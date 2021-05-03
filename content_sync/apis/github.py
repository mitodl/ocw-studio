""" Github API wrapper"""
import logging
from base64 import b64decode
from typing import Iterator

import yaml
from django.conf import settings
from django.db.models import F, Q
from github import ContentFile, Github, GithubException, InputGitTreeElement
from github.Branch import Branch
from github.Commit import Commit
from github.InputGitAuthor import InputGitAuthor
from github.Repository import Repository

from content_sync.decorators import retry_on_failure
from content_sync.models import ContentSyncState
from main import features
from ocw_import.api import convert_data_to_content
from users.models import User
from websites.models import WebsiteContent


log = logging.getLogger(__name__)

GIT_DATA_FILEPATH = "filepath"


class GithubApiWrapper:
    """
    Github API wrapper class
    """

    def __init__(self, website: WebsiteContent):
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
        self, website_content: WebsiteContent, message: str, **kwargs
    ) -> Commit:
        """
        Create or update a file in git.
        """
        if not website_content.content_filepath:
            # No filepath, nothing to do"
            return
        repo = self.get_repo()
        path = website_content.content_filepath
        data = self.format_content_to_file(website_content)
        git_user = self.git_user(website_content.updated_by)
        try:
            sha = repo.get_contents(path).sha
        except:  # pylint:disable=bare-except
            return repo.create_file(
                path, message, data, committer=git_user, author=git_user, **kwargs
            )
        return repo.update_file(
            path, message, data, sha, committer=git_user, author=git_user, **kwargs
        )

    def upsert_content_files(self):
        """ Commit all website content, with 1 commit per user """
        for user_id in self.website.websitecontent_set.values_list(
            "updated_by", flat=True
        ).distinct():
            self.upsert_content_files_for_user(user_id)

    @retry_on_failure
    def upsert_content_files_for_user(  # pylint:disable=too-many-locals
        self, user_id=None, **kwargs
    ) -> Commit:
        """
        Upsert multiple WebsiteContent objects to github in one commit
        """
        unsynced_states = ContentSyncState.objects.filter(
            Q(content__website=self.website) & Q(content__updated_by=user_id)
        ).exclude(
            Q(current_checksum=F("synced_checksum")) & Q(synced_checksum__isnull=False)
        )
        repo = self.get_repo()
        main_ref = repo.get_git_ref(f"heads/{settings.GIT_BRANCH_MAIN}")
        main_sha = main_ref.object.sha
        base_tree = repo.get_git_tree(main_sha)
        modified_element_list = []
        synced_filepaths = {}

        for sync_state in unsynced_states.iterator():
            content = sync_state.content
            filepath = content.content_filepath  # TO DO: Use dynamic filepath
            # Add any modified files
            if filepath:
                synced_filepaths.update({sync_state.id: filepath})
                data = self.format_content_to_file(content)
                modified_element_list.append(
                    InputGitTreeElement(filepath, "100644", "blob", data)
                )
                # Remove the old filepath stored in the sync state data if it doesn't match current path
                if (
                    sync_state.data
                    and sync_state.data.get(GIT_DATA_FILEPATH, None)
                    and sync_state.data[GIT_DATA_FILEPATH] != filepath
                ):
                    modified_element_list.append(
                        InputGitTreeElement(
                            sync_state.data[GIT_DATA_FILEPATH],
                            "100644",
                            "blob",
                            sha=None,
                        )
                    )

        if len(modified_element_list) > 0:
            tree = repo.create_git_tree(modified_element_list, base_tree)
            parent = repo.get_git_commit(main_sha)
            git_user = self.git_user(User.objects.filter(id=user_id).first())
            commit = repo.create_git_commit(
                "Sync all content",
                tree,
                [parent],
                committer=git_user,
                author=git_user,
                **kwargs,
            )
            main_ref.edit(commit.sha)

            # Mark all as synced
            for synced_state_id, filepath in synced_filepaths.items():
                sync_state = ContentSyncState.objects.get(id=synced_state_id)
                sync_state.current_checksum = content.calculate_checksum()
                sync_state.data = {GIT_DATA_FILEPATH: filepath}
                sync_state.mark_synced()
            return commit

    @retry_on_failure
    def delete_content_file(self, content: WebsiteContent) -> Commit:
        """
        Delete a file from git
        """
        repo = self.get_repo()
        sha = repo.get_contents(content.content_filepath).sha
        return repo.delete_file(
            content.content_filepath,
            f"Delete {content.content_filepath}",
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

    def format_content_to_file(self, website_content: WebsiteContent) -> str:
        """
        This is a temporary function to convert WebsiteContent metadata + markdown into a format
        suitable for Hugo.  It should be modified or removed once a more permanent solution for that
        functionality is implemented.
        """
        return f"---\n{yaml.dump(website_content.metadata)}\n---\n{website_content.markdown}"

    def format_file_to_content(self, content_file: ContentFile) -> WebsiteContent:
        """
        This is a temporary function to convert a git file to a WebsiteContent object.  It should be
        modified or removed once a more permanent solution for that functionality is implemented.
        For now it is using the same code as the import_ocw_course_files command.
        """
        return convert_data_to_content(
            content_file.path,
            str(b64decode(content_file.content), encoding="utf-8"),
            self.website,
            self.website.uuid,
        )
