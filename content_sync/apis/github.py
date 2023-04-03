""" Github API wrapper"""
import logging
from base64 import b64decode
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional
from urllib.parse import urlparse

import requests
import yaml
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F, Q
from github import (
    Consts,
    ContentFile,
    Github,
    GithubException,
    GithubIntegration,
    InputGitTreeElement,
)
from github.Branch import Branch
from github.Commit import Commit
from github.InputGitAuthor import InputGitAuthor
from github.Repository import Repository
from safedelete.models import HARD_DELETE
from yamale import YamaleError

from content_sync.decorators import retry_on_failure
from content_sync.models import ContentSyncState
from content_sync.serializers import serialize_content_to_file
from content_sync.utils import get_destination_filepath
from main import features
from users.models import User
from websites.api import get_valid_new_slug
from websites.config_schema.api import validate_raw_site_config
from websites.constants import STARTER_SOURCE_GITHUB
from websites.models import (
    Website,
    WebsiteContent,
    WebsiteContentQuerySet,
    WebsiteStarter,
)
from websites.site_config_api import SiteConfig


log = logging.getLogger(__name__)

GIT_DATA_FILEPATH = "filepath"


@dataclass
class SyncResult:
    """ The result of syncing a file to github """

    sync_id: int
    filepath: str
    checksum: str
    deleted: bool = False


def decode_file_contents(content_file: ContentFile) -> str:
    """
    Decode repo file contents from base64 to a normal string.
    """
    return str(b64decode(content_file.content), encoding="utf-8")


def sync_starter_configs(  # pylint:disable=too-many-locals
    repo_url: str, config_files: List[str], commit: Optional[str] = None
):
    """
    Create/update WebsiteStarter objects given a repo URL and a list of config files in the repo.
    If a commit was passed in and GITHUB_WEBHOOK_BRANCH is set, these are compared and the change
    is ignored if it does not match the branch in settings.
    """
    repo_path = urlparse(repo_url).path.lstrip("/")
    org_name, repo_name = repo_path.split("/", 1)
    git = Github()
    org = git.get_organization(org_name)
    repo = org.get_repo(repo_name)

    settings_branch = settings.GITHUB_WEBHOOK_BRANCH
    branch = (
        repo.get_branch(settings_branch)
        if settings_branch
        else repo.get_branch(repo.default_branch)
    )
    if commit is not None and commit != branch.commit.sha:
        return

    for config_file in config_files:
        try:
            git_file = repo.get_contents(config_file, commit)
            slug = (
                git_file.path.split("/")[0]
                if git_file.path != settings.OCW_STUDIO_SITE_CONFIG_FILE
                else repo_name
            )
            path = "/".join([repo_url, slug])
            unique_slug = get_valid_new_slug(slug, path)
            raw_yaml = git_file.decoded_content
            validate_raw_site_config(raw_yaml.decode("utf-8"))
            config = yaml.load(raw_yaml, Loader=yaml.SafeLoader)
            starter, created = WebsiteStarter.objects.update_or_create(
                source=STARTER_SOURCE_GITHUB,
                path=path,
                defaults={"config": config, "commit": commit, "slug": unique_slug},
            )
            # Give the WebsiteStarter a name equal to the slug if created, otherwise keep the current value.
            if created:
                starter.name = starter.slug
                starter.save()
        except YamaleError:
            log.exception("Invalid site config YAML found in %s", config_file)
            continue
        except:  # pylint: disable=bare-except
            log.exception("Error processing config file %s", config_file)
            continue


def get_app_installation_id(app: GithubIntegration) -> Optional[str]:
    """
    Get the app installation id for the organization
    """
    headers = {
        "Authorization": f"Bearer {app.create_jwt(expiration=600)}",
        "Accept": Consts.mediaTypeIntegrationPreview,
        "User-Agent": "PyGithub/Python",
    }

    response = requests.get(
        f"{app.base_url}/app/installations",
        headers=headers,
    )
    response.raise_for_status()
    response_dict = response.json()
    if response_dict:
        for git_app in response_dict:
            if git_app["app_id"] == settings.GITHUB_APP_ID:
                return git_app["id"]


def get_token():
    """ Get a github token for requests """
    if settings.GITHUB_APP_ID and settings.GITHUB_APP_PRIVATE_KEY:
        try:
            app = GithubIntegration(
                settings.GITHUB_APP_ID,
                default_backend().load_pem_private_key(
                    settings.GITHUB_APP_PRIVATE_KEY,
                    None,
                    unsafe_skip_rsa_key_validation=False,
                ),
                **(
                    {"base_url": settings.GIT_API_URL}
                    if settings.GIT_API_URL is not None
                    else {}
                ),
            )
            return app.get_access_token(get_app_installation_id(app)).token
        except (requests.HTTPError, ValueError, TypeError) as exc:
            raise ImproperlyConfigured(
                "Could not initialize github app, check the relevant settings"
            ) from exc
    elif settings.GIT_TOKEN:
        return settings.GIT_TOKEN
    else:
        raise ImproperlyConfigured(
            "Missing Github settings, a token or app id and private key are required"
        )


class GithubApiWrapper:
    """
    Github API wrapper class
    """

    def __init__(self, website: Website, site_config: Optional[SiteConfig] = None):
        """ Initialize the Github API backend for a specific website"""
        self.website = website
        self.site_config = site_config or SiteConfig(self.website.starter.config)
        self.repo = None
        self.git = Github(
            login_or_token=get_token(),
            **(
                {"base_url": settings.GIT_API_URL}
                if settings.GIT_API_URL is not None
                else {}
            ),
        )
        self.org = self.git.get_organization(settings.GIT_ORGANIZATION)

    @retry_on_failure
    def get_repo(self) -> Repository:
        """
        Get the website repo, create if necessary
        """
        if not self.repo:
            try:
                self.repo = self.org.get_repo(self.website.short_id)
            except GithubException as ge:
                if ge.status == 404:
                    self.repo = self.create_repo()
                else:
                    raise
        return self.repo

    @retry_on_failure
    def repo_exists(self):
        """Return True if the repo already exists"""
        try:
            self.org.get_repo(self.website.short_id)
            return True
        except GithubException as ge:
            if ge.status == 404:
                return False
            else:
                raise
        return False

    @retry_on_failure
    def create_repo(self, **kwargs) -> Repository:
        """
        Create a website repo
        """
        try:
            self.repo = self.org.create_repo(
                self.website.short_id, auto_init=True, **kwargs
            )
        except GithubException as ge:
            if ge.status == 422:
                # It may already exist, try to retrieve it
                self.repo = self.org.get_repo(self.website.short_id)
                log.debug("Repo already exists: %s", self.website.name)
        if self.repo.default_branch != settings.GIT_BRANCH_MAIN:
            self.rename_branch(self.repo.default_branch, settings.GIT_BRANCH_MAIN)
        existing_branches = [branch.name for branch in self.repo.get_branches()]
        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            if branch not in existing_branches:
                self.create_branch(branch, settings.GIT_BRANCH_MAIN)
        return self.repo

    @retry_on_failure
    def get_branches(self) -> Iterator[Branch]:
        """
        Yield all the branches in a repo.
        """
        for branch in self.get_repo().get_branches():
            yield branch

    def rename_branch(self, from_name: str, to_name: str) -> Branch:
        """
        Rename a git branch
        """
        return self.create_branch(to_name, from_name, delete_source=True)

    @retry_on_failure
    def create_branch(self, branch: str, source: str, delete_source=False) -> Branch:
        """
        Create a new git branch, and optionally delete the source branch afterward.
        """
        repo = self.get_repo()
        source_branch = repo.get_git_ref(f"heads/{source}")
        try:
            new_branch = repo.create_git_ref(
                f"refs/heads/{branch}", sha=source_branch.object.sha
            )
        except GithubException as ge:
            if ge.status == 422:
                # It may already exist
                new_branch = repo.get_git_ref(f"heads/{branch}")
            else:
                raise
        if delete_source:
            source_branch.delete()
        return new_branch

    @retry_on_failure
    def upsert_content_file(
        self, website_content: WebsiteContent, **kwargs
    ) -> Optional[Commit]:
        """
        Create or update a file in git.
        """
        destination_filepath = get_destination_filepath(
            website_content, self.site_config
        )
        if not destination_filepath:
            # No filepath, nothing to do
            return
        repo = self.get_repo()
        data = serialize_content_to_file(
            site_config=self.site_config, website_content=website_content
        )
        git_user = self.git_user(website_content.updated_by)
        try:
            sha = repo.get_contents(destination_filepath).sha
        except:  # pylint:disable=bare-except
            return repo.create_file(
                destination_filepath,
                f"Create {destination_filepath}",
                data,
                committer=git_user,
                author=git_user,
                **kwargs,
            )
        return repo.update_file(
            destination_filepath,
            f"Update {destination_filepath}",
            data,
            sha,
            committer=git_user,
            author=git_user,
            **kwargs,
        )

    def upsert_content_files(self, query_set: Optional[WebsiteContentQuerySet] = None):
        """ Commit all website content, with 1 commit per user, optionally filtering with a QuerySet """
        if query_set:
            content_files = query_set.values_list("updated_by", flat=True).distinct()
        else:
            content_files = (
                WebsiteContent.objects.all_with_deleted()
                .filter(website=self.website)
                .values_list("updated_by", flat=True)
                .distinct()
            )
        for user_id in content_files:
            self.upsert_content_files_for_user(user_id, query_set)

    @retry_on_failure
    def upsert_content_files_for_user(
        self, user_id=None, query_set: Optional[WebsiteContentQuerySet] = None
    ) -> Optional[Commit]:
        """
        Upsert multiple WebsiteContent objects to github in one commit, optionally filtering with a QuerySet
        """
        unsynced_states = ContentSyncState.objects.filter(
            Q(content__website=self.website) & Q(content__updated_by=user_id)
        ).exclude(
            Q(current_checksum=F("synced_checksum"), content__deleted__isnull=True)
            & Q(synced_checksum__isnull=False)
        )
        if query_set:
            unsynced_states = unsynced_states.filter(content__in=query_set)
        modified_element_list = []
        synced_results = []

        for sync_state in unsynced_states.iterator():
            content = sync_state.content
            filepath = get_destination_filepath(content, self.site_config)
            if not filepath:
                continue
            current_checksum = content.calculate_checksum()
            if sync_state.current_checksum != current_checksum:
                # sync_state.current_checksum is out of date
                sync_state.current_checksum = current_checksum
                sync_state.save()
                if (
                    current_checksum == sync_state.synced_checksum
                    and not content.deleted
                ):
                    continue
            synced_results.append(
                SyncResult(
                    sync_id=sync_state.id,
                    filepath=filepath,
                    checksum=current_checksum,
                    deleted=content.deleted is not None,
                )
            )
            data = serialize_content_to_file(
                site_config=self.site_config, website_content=content
            )
            # Add any modified files
            modified_element_list.extend(
                self.get_tree_elements(sync_state, data, filepath)
            )

        if len(modified_element_list) == 0:
            return

        commit = self.commit_tree(
            modified_element_list, User.objects.filter(id=user_id).first()
        )

        # Save last git filepath and checksum to sync state
        for sync_result in synced_results:
            sync_state = ContentSyncState.objects.get(id=sync_result.sync_id)
            if sync_result.deleted:
                sync_state.content.delete(force_policy=HARD_DELETE)
            else:
                sync_state.data = {GIT_DATA_FILEPATH: sync_result.filepath}
                sync_state.synced_checksum = sync_result.checksum
                sync_state.save()

        return commit

    @retry_on_failure
    def delete_content_file(self, content: WebsiteContent) -> Commit:
        """
        Delete a file from git
        """
        repo = self.get_repo()
        filepath = get_destination_filepath(content, self.site_config)
        sha = repo.get_contents(filepath).sha
        return repo.delete_file(
            filepath,
            f"Delete {filepath}",
            sha,
            committer=self.git_user(content.updated_by),
        )

    @retry_on_failure
    def merge_branches(self, from_branch: str, to_branch: str) -> Commit:
        """
        Merge one branch to another
        """
        repo = self.get_repo()
        head_sha = repo.get_branch(from_branch).commit.sha
        return repo.merge(to_branch, head_sha, f"Merge {from_branch} to {to_branch}")

    def git_user(self, user: User) -> InputGitAuthor:
        """
        Return an InputGitAuthor object to be used as a committer.
        Applies default settings for name and email if the input User is None.
        """
        name = settings.GIT_DEFAULT_USER_NAME
        email = settings.GIT_DEFAULT_USER_EMAIL
        if user:
            if features.is_enabled(features.GIT_ANONYMOUS_COMMITS):
                name = f"user_{user.id}"
            else:
                name = user.name or user.username
                email = user.email
        return InputGitAuthor(name, email)

    def get_tree_elements(
        self, sync_state: ContentSyncState, data: str, filepath: str
    ) -> List[InputGitTreeElement]:
        """
        Return the required InputGitTreeElements for a modified ContentSyncState
        """
        tree_elements = []
        # Update with the new file data only if the content isn't deleted
        if sync_state.content.deleted is None:
            tree_elements.append(InputGitTreeElement(filepath, "100644", "blob", data))
        if sync_state.data is None:
            return tree_elements
        # Remove the old filepath stored in the sync state data
        if (
            # If it has been deleted
            sync_state.content.deleted is not None
            or (
                # If it doesn't match current path
                sync_state.data.get(GIT_DATA_FILEPATH, None)
                and sync_state.data[GIT_DATA_FILEPATH] != filepath
            )
        ):
            tree_elements.append(
                InputGitTreeElement(
                    sync_state.data[GIT_DATA_FILEPATH],
                    "100644",
                    "blob",
                    sha=None,
                )
            )
        return tree_elements

    def commit_tree(self, element_list: [InputGitTreeElement], user: User) -> Commit:
        """
        Create a commit containing all the changes specified in a list of InputGitTreeElements
        """
        repo = self.get_repo()
        main_ref = repo.get_git_ref(f"heads/{settings.GIT_BRANCH_MAIN}")
        main_sha = main_ref.object.sha
        base_tree = repo.get_git_tree(main_sha)
        tree = repo.create_git_tree(element_list, base_tree)
        parent = repo.get_git_commit(main_sha)
        git_user = self.git_user(user)
        commit = repo.create_git_commit(
            "Sync all content", tree, [parent], committer=git_user, author=git_user
        )
        main_ref.edit(commit.sha)
        return commit

    def get_all_file_paths(self, path: str) -> Iterable[str]:
        """Yield all file paths in the repo"""
        for content in self.get_repo().get_contents(path):
            if content.type == "file" and content.path != "README.md":
                yield content.path
            elif content.type == "dir":
                yield from self.get_all_file_paths(content.path)

    def batch_delete_files(self, paths: List[str], user: Optional[User] = None):
        """Batch delete multiple git files in a single commit"""
        tree_elements = [
            InputGitTreeElement(
                path,
                "100644",
                "blob",
                sha=None,
            )
            for path in paths
        ]
        if tree_elements:
            self.commit_tree(tree_elements, user)
