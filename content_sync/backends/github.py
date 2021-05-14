""" Github backend """
import logging

from django.conf import settings
from github.Commit import Commit
from github.ContentFile import ContentFile
from github.PullRequest import PullRequest
from github.Repository import Repository
from safedelete.models import HARD_DELETE

from content_sync.apis.github import GithubApiWrapper, decode_file_contents
from content_sync.backends.base import BaseSyncBackend
from content_sync.decorators import check_sync_state
from content_sync.models import ContentSyncState
from content_sync.serializers import deserialize_file_to_website_content
from websites.models import Website, WebsiteContent


log = logging.getLogger(__name__)


class GithubBackend(BaseSyncBackend):
    """
    Github backend
    """

    IGNORED_PATHS = {"README.md"}

    def __init__(self, website: Website):
        """ Initialize the Github API backend for a specific website"""
        super().__init__(website)
        self.api = GithubApiWrapper(self.website, self.site_config)

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
        return self.api.upsert_content_file(content)

    @check_sync_state
    def update_content_in_backend(self, sync_state: ContentSyncState) -> Commit:
        """
        Update content in Github.
        """
        content = sync_state.content
        return self.api.upsert_content_file(content)

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
        content.delete(force_policy=HARD_DELETE)
        return commit

    def create_content_in_db(self, data: ContentFile) -> WebsiteContent:
        """
        Create a WebsiteContent object from a github file
        """
        return deserialize_file_to_website_content(
            site_config=self.site_config,
            website=self.website,
            filepath=data.path,
            file_contents=decode_file_contents(data),
        )

    def update_content_in_db(self, data: ContentFile) -> WebsiteContent:
        """
        Update a WebsiteContent object from a github file
        """
        return deserialize_file_to_website_content(
            site_config=self.site_config,
            website=self.website,
            filepath=data.path,
            file_contents=decode_file_contents(data),
        )

    def delete_content_in_db(self, data: ContentSyncState) -> bool:
        """
        Delete a WebsiteContent object
        """
        content = data.content
        content.delete(force_policy=HARD_DELETE)
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
            elif (
                file_content.type == "file"
                and file_content.path not in self.IGNORED_PATHS
            ):
                content = deserialize_file_to_website_content(
                    site_config=self.site_config,
                    website=self.website,
                    filepath=file_content.path,
                    file_contents=decode_file_contents(file_content),
                )
                sync_state = content.content_sync_state
                sync_state.current_checksum = content.calculate_checksum()
                sync_state.synced_checksum = sync_state.current_checksum
                sync_state.save()
                if content.id in website_content_ids:
                    website_content_ids.remove(content.id)

        # Delete any WebsiteContent ids still remaining
        # we use a hard delete because there's no need to sync a deletion to
        # the repo when it already doesn't exist
        self.website.websitecontent_set.filter(id__in=website_content_ids).delete(
            force_policy=HARD_DELETE
        )
