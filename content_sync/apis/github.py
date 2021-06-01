""" Github API wrapper"""
import logging
import os
from base64 import b64decode
from dataclasses import dataclass
from typing import Iterator, List, Optional
from urllib.parse import urlparse

import yaml
from django.conf import settings
from django.db.models import F, Q
from github import ContentFile, Github, GithubException, InputGitTreeElement
from github.Branch import Branch
from github.Commit import Commit
from github.InputGitAuthor import InputGitAuthor
from github.Repository import Repository
from safedelete.models import HARD_DELETE

from content_sync.decorators import retry_on_failure
from content_sync.models import ContentSyncState
from content_sync.serializers import serialize_content_to_file
from main import features
from users.models import User
from websites.constants import WEBSITE_CONTENT_FILETYPE, STARTER_SOURCE_GITHUB
from websites.models import Website, WebsiteContent, WebsiteStarter
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
    return str(b64decode(content_file.content), encoding="utf-8")


def get_destination_filepath(
    content: WebsiteContent, site_config: SiteConfig
) -> Optional[str]:
    """
    Returns the full filepath where the equivalent file for the WebsiteContent record should be placed
    """
    if content.is_page_content:
        return os.path.join(
            content.dirpath, f"{content.filename}.{WEBSITE_CONTENT_FILETYPE}"
        )
    config_item = site_config.find_item_by_name(name=content.type)
    if config_item is None:
        log.error(
            "Config item not found (content: %s, name value missing from config: %s)",
            (content.id, content.text_id),
            content.type,
        )
        return None
    if config_item.is_file_item():
        return config_item.file_target
    log.error(
        "Invalid config item: is_page_content flag is False, and config item is not 'file'-type (content: %s)",
        (content.id, content.text_id),
    )
    return None


def sync_starter_configs(repo_url: str, config_files: List[str]):
    """
    Create/update WebsiteStarter objects given a repo URL and a list of config files in the repo.
    """
    repo_path = urlparse(repo_url).path.lstrip("/")
    org_name, repo_name = repo_path.split("/", 1)
    log.error(f"{repo_path}, {org_name}, {repo_name}")
    git_api = Github(login_or_token=settings.GIT_TOKEN)
    org = git_api.get_organization(org_name)
    repo = org.get_repo(repo_name)

    for config_file in config_files:
        git_file = repo.get_contents(config_file)
        slug = (
            git_file.path.split("/")[0]
            if git_file.path != settings.OCW_STUDIO_SITE_CONFIG_FILE
            else repo_name
        )
        config = yaml.load(git_file.decoded_content, Loader=yaml.Loader)
        starter, created = WebsiteStarter.objects.update_or_create(
            source=STARTER_SOURCE_GITHUB,
            path="/".join([repo_url, slug]),
            defaults={"slug": slug, "config": config},
        )
        # Give the WebsiteStarter a name equal to the slug if created, otherwise keep the current value.
        if created:
            starter.name = starter.slug
            starter.save()


class GithubApiWrapper:
    """
    Github API wrapper class
    """

    def __init__(self, website: Website, site_config: Optional[SiteConfig]):
        """ Initialize the Github API backend for a specific website"""
        self.git = Github(
            login_or_token=settings.GIT_TOKEN,
            **(
                {"base_url": settings.GIT_API_URL}
                if settings.GIT_API_URL is not None
                else {}
            ),
        )
        self.org = self.git.get_organization(settings.GIT_ORGANIZATION)
        self.website = website
        self.site_config = site_config or SiteConfig(self.website.starter.config)
        self.repo = None

    def get_repo_name(self):
        """Determine a 100-char-limit repo name based on the website name and uuid"""
        return f"{self.website.name[:67]}_{self.website.uuid.hex}"

    @retry_on_failure
    def get_repo(self) -> Repository:
        """
        Get the website repo, create if necessary
        """
        if not self.repo:
            try:
                self.repo = self.org.get_repo(self.get_repo_name())
            except GithubException as ge:
                if ge.status == 404:
                    self.repo = self.create_repo()
                else:
                    raise
        return self.repo

    @retry_on_failure
    def create_repo(self, **kwargs) -> Repository:
        """
        Create a website repo
        """
        try:
            self.repo = self.org.create_repo(
                self.get_repo_name(), auto_init=True, **kwargs
            )
        except GithubException as ge:
            if ge.status == 422:
                # It may already exist, try to retrieve it
                self.repo = self.org.get_repo(self.get_repo_name())
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

    def upsert_content_files(self):
        """ Commit all website content, with 1 commit per user """
        for user_id in (
            WebsiteContent.objects.all_with_deleted()
            .filter(website=self.website)
            .values_list("updated_by", flat=True)
            .distinct()
        ):
            self.upsert_content_files_for_user(user_id)

    @retry_on_failure
    def upsert_content_files_for_user(self, user_id=None) -> Optional[Commit]:
        """
        Upsert multiple WebsiteContent objects to github in one commit
        """
        unsynced_states = ContentSyncState.objects.filter(
            Q(content__website=self.website) & Q(content__updated_by=user_id)
        ).exclude(
            Q(current_checksum=F("synced_checksum"), content__deleted__isnull=True)
            & Q(synced_checksum__isnull=False)
        )
        modified_element_list = []
        synced_results = []

        for sync_state in unsynced_states.iterator():
            content = sync_state.content
            filepath = get_destination_filepath(content, self.site_config)
            if not filepath:
                continue
            synced_results.append(
                SyncResult(
                    sync_id=sync_state.id,
                    filepath=filepath,
                    checksum=content.calculate_checksum(),
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
