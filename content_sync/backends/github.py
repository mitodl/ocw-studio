""" Github backend """
import logging

from django.conf import settings
from github.Commit import Commit
from github.ContentFile import ContentFile
from github.PullRequest import PullRequest
from github.Repository import Repository

from content_sync.apis.github import GithubApiWrapper
from content_sync.backends.base import BaseSyncBackend
from content_sync.decorators import check_sync_state
from content_sync.models import ContentSyncState
from websites.models import WebsiteContent


log = logging.getLogger(__name__)


class GithubBackend(BaseSyncBackend):
    """
    Github backend
    """

    def __init__(self, website: WebsiteContent):
        """ Initialize the Github API backend for a specific website"""
        self.api = GithubApiWrapper(website)
        super().__init__(website)

    def create_website_in_backend(self) -> Repository:
        """
        Create a Website git repo with 3 branches.  Requires ~6 API calls.
        """
        return self.api.create_repo()

    def create_backend_preview(self) -> PullRequest:
        """
        Sync all content to main branch then merge main branch to preview branch
        """
        self.sync_all_content_to_backend()
        return self.api.merge_branches(
            settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
        )

    def create_backend_release(self) -> PullRequest:
        """
        Merge preview branch to release branch
        """
        return self.api.merge_branches(
            settings.GIT_BRANCH_PREVIEW,
            settings.GIT_BRANCH_RELEASE,
        )

    @check_sync_state
    def create_content_in_backend(self, sync_state: ContentSyncState) -> Commit:
        """
        Create new content in Github.
        """
        content = sync_state.content
        return self.api.upsert_content_file(
            content,
            f"Create {content.content_filepath}",
        )

    @check_sync_state
    def update_content_in_backend(self, sync_state: ContentSyncState) -> Commit:
        """
        Update content in Github.
        """
        content = sync_state.content
        return self.api.upsert_content_file(
            content, f"Modify {content.content_filepath}"
        )

    def sync_all_content_to_backend(self) -> Commit:
        """
        Sync all the website's files to Github in one commit
        """
        return self.api.upsert_content_files()

    def delete_content_in_backend(self, sync_state: ContentSyncState) -> Commit:
        """
        Delete content from Github
        """
        content = sync_state.content
        commit = self.api.delete_content_file(content)
        sync_state.delete()
        content.delete()
        return commit

    def create_content_in_db(self, data: ContentFile) -> WebsiteContent:
        """
        Create a WebsiteContent object from a github file
        """
        return self.api.format_file_to_content(data)

    def update_content_in_db(self, data: ContentFile) -> WebsiteContent:
        """
        Update a WebsiteContent object from a github file
        """
        return self.api.format_file_to_content(data)

    def delete_content_in_db(self, data: ContentSyncState) -> bool:
        """
        Delete a WebsiteContent object
        """
        content = data.content
        data.delete()
        content.delete()
        return True

    def sync_all_content_to_db(self):
        """
        Iterate over a website's WebsiteContent objects, deleting any that don't exist in the git repo.
        Then recursively iterate through the repo, upserting any ContentFiles to WebsiteContent objects.
        """
        repo = self.api.get_repo()

        # Get list of existing WebsiteContent ids for the website
        website_content_ids = list(
            self.website.websitecontent_set.all().values_list("id", flat=True)
        )

        # Iterate over repo files
        contents = repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            elif file_content.type == "file":
                content = self.api.format_file_to_content(file_content)
                sync_state = content.content_sync_state
                sync_state.current_checksum = content.calculate_checksum()
                sync_state.synced_checksum = sync_state.current_checksum
                sync_state.save()
                if content.id in website_content_ids:
                    website_content_ids.remove(content.id)

        # Delete any WebsiteContent ids still remaining
        for content in self.website.websitecontent_set.filter(
            id__in=website_content_ids
        ):
            if hasattr(content, "content_sync_state"):
                content.content_sync_state.delete()
            content.delete()
