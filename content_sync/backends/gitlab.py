"""GitLab backend"""

import logging

from django.conf import settings
from safedelete.models import HARD_DELETE

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.apis.gitlab import GitlabApiWrapper, decode_file_contents
from content_sync.backends.base import BaseSyncBackend
from content_sync.decorators import check_sync_state
from content_sync.models import ContentSyncState
from content_sync.serializers import deserialize_file_to_website_content
from content_sync.utils import get_destination_filepath
from websites.models import Website, WebsiteContent, WebsiteContentQuerySet

log = logging.getLogger(__name__)


class GitlabBackend(BaseSyncBackend):
    """GitLab backend."""

    IGNORED_PATHS = {"README.md"}
    rate_limit_name = "gitlab"
    rate_limit_check_setting = "GITLAB_RATE_LIMIT_CHECK"
    rate_limit_cutoff_setting = "GITLAB_RATE_LIMIT_CUTOFF"
    rate_limit_min_sleep_setting = "GITLAB_RATE_LIMIT_MIN_SLEEP"

    def __init__(self, website: Website):
        """Initialize the GitLab API backend for a specific website."""
        super().__init__(website)
        self.api = GitlabApiWrapper(self.website, self.site_config)

    def backend_exists(self):
        """Determine if the website repo exists."""
        return self.api.repo_exists()

    def get_rate_limit_status(self):
        """Return GitLab rate limit state if available."""
        return self.api.get_rate_limit_status()

    def create_website_in_backend(self):
        """Create a Website git repo with main/preview/release branches."""
        return self.api.create_repo()

    def merge_backend_draft(self):
        """Sync all content to main branch then merge main branch to preview branch."""
        self.sync_all_content_to_backend()
        return self.api.merge_branches(
            settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
        )

    def merge_backend_live(self):
        """Merge main branch to preview and release branches."""
        self.merge_backend_draft()
        return self.api.merge_branches(
            settings.GIT_BRANCH_MAIN,
            settings.GIT_BRANCH_RELEASE,
        )

    @check_sync_state
    def create_content_in_backend(self, sync_state: ContentSyncState):
        """Create new content in GitLab."""
        return self.api.upsert_content_file(sync_state.content)

    @check_sync_state
    def update_content_in_backend(self, sync_state: ContentSyncState):
        """Update content in GitLab."""
        return self.api.upsert_content_file(sync_state.content)

    def delete_orphaned_content_in_backend(self):
        """Delete any git repo files without corresponding WebsiteContent objects."""
        sitepaths = []
        for content in self.website.websitecontent_set.iterator():
            sitepaths.append(get_destination_filepath(content, self.site_config))
            if content.content_sync_state.data and content.content_sync_state.data.get(
                GIT_DATA_FILEPATH, None
            ):
                sitepaths.append(content.content_sync_state.data[GIT_DATA_FILEPATH])
        self.api.batch_delete_files(
            [path for path in self.api.get_all_file_paths("") if path not in sitepaths]
        )

    def sync_all_content_to_backend(
        self,
        query_set: WebsiteContentQuerySet | None = None,
        *,
        use_batch_commits: bool = False,
        batch_size: int | None = None,
    ):
        """Sync all the website's files to GitLab in one commit."""
        return self.api.upsert_content_files(
            query_set=query_set,
            use_batch_commits=use_batch_commits,
            batch_size=batch_size,
        )

    def delete_content_in_backend(self, sync_state: ContentSyncState):
        """Delete content from GitLab."""
        content = sync_state.content
        commit = self.api.delete_content_file(content)
        content.delete(force_policy=HARD_DELETE)
        return commit

    def create_content_in_db(self, data: object) -> WebsiteContent:
        """Create a WebsiteContent object from a GitLab file."""
        return deserialize_file_to_website_content(
            site_config=self.site_config,
            website=self.website,
            filepath=data.file_path,
            file_contents=decode_file_contents(data),
        )

    def update_content_in_db(self, data: object) -> WebsiteContent:
        """Update a WebsiteContent object from a GitLab file."""
        return deserialize_file_to_website_content(
            site_config=self.site_config,
            website=self.website,
            filepath=data.file_path,
            file_contents=decode_file_contents(data),
        )

    def delete_content_in_db(self, data: ContentSyncState) -> bool:
        """Delete a WebsiteContent object."""
        content = data.content
        content.delete(force_policy=HARD_DELETE)
        return True

    def sync_all_content_to_db(self, ref: str | None = None, path: str | None = None):
        """Sync all WebsiteContent records from GitLab into the database."""
        repo = self.api.get_repo()

        website_content_ids = list(
            self.website.websitecontent_set.all().values_list("id", flat=True)
        )
        ref_to_use = ref or settings.GIT_BRANCH_MAIN
        tree = repo.repository_tree(path=path or "", ref=ref_to_use, recursive=True)

        for item in tree:
            if item.get("type") != "blob":
                continue
            file_path = item.get("path")
            if file_path in self.IGNORED_PATHS or (
                path is not None and file_path != path
            ):
                continue

            file_content = repo.files.get(file_path=file_path, ref=ref_to_use)
            content = self.update_content_in_db(file_content)
            sync_state = content.content_sync_state
            sync_state.current_checksum = content.calculate_checksum()
            if ref is None:
                sync_state.synced_checksum = sync_state.current_checksum
            sync_state.save()

            if content.id in website_content_ids:
                website_content_ids.remove(content.id)

        if ref is None and not path:
            self.website.websitecontent_set.filter(id__in=website_content_ids).delete(
                force_policy=HARD_DELETE
            )
