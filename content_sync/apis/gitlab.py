"""GitLab API wrapper"""

import logging
from base64 import b64decode
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import gitlab
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F, Q
from gitlab.exceptions import (
    GitlabCreateError,
    GitlabDeleteError,
    GitlabGetError,
    GitlabMRClosedError,
    GitlabUpdateError,
)
from safedelete.models import HARD_DELETE

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.decorators import retry_on_failure
from content_sync.models import ContentSyncState
from content_sync.serializers import serialize_content_to_file
from content_sync.utils import get_destination_filepath
from main import features
from users.models import User
from websites.models import Website, WebsiteContent, WebsiteContentQuerySet
from websites.site_config_api import SiteConfig

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """The result of syncing a file to GitLab."""

    sync_id: int
    filepath: str
    checksum: str
    deleted: bool = False


def decode_file_contents(content_file: object) -> str:
    """Decode GitLab file contents from base64 to a normal string."""
    return str(b64decode(content_file.content), encoding="utf-8")


def get_token() -> str:
    """Get a GitLab token for requests."""
    if settings.GIT_TOKEN:
        return settings.GIT_TOKEN
    msg = "Missing GitLab settings, GIT_TOKEN is required"
    raise ImproperlyConfigured(msg)


def update_all_repos_visibility(visibility: str = "public") -> int:
    """Update visibility for all repos in the configured GitLab group.

    Returns the number of repos updated.
    """
    gl = gitlab.Gitlab(
        url=settings.GIT_API_URL,
        private_token=get_token(),
        timeout=settings.GITLAB_TIMEOUT,
    )
    group = gl.groups.get(settings.GIT_ORGANIZATION)
    count = 0
    page = 1
    per_page = 100

    while True:
        # Use explicit page params rather than get_all=True so we don't
        # depend on potentially incorrect next-link URLs returned by GitLab.
        projects = group.projects.list(page=page, per_page=per_page)
        if not projects:
            break

        for stub in projects:
            project = gl.projects.get(stub.id)
            if project.visibility != visibility:
                project.visibility = visibility
                project.save()
                count += 1

        page += 1

    return count


class GitlabApiWrapper:
    """GitLab API wrapper class."""

    def __init__(self, website: Website, site_config: SiteConfig | None = None):
        """Initialize the GitLab API backend for a specific website."""
        if not settings.GIT_API_URL:
            msg = "Missing GitLab settings, GIT_API_URL is required"
            raise ImproperlyConfigured(msg)
        if not settings.GIT_ORGANIZATION:
            msg = "Missing GitLab settings, GIT_ORGANIZATION is required"
            raise ImproperlyConfigured(msg)
        self.website = website
        self.site_config = site_config or SiteConfig(self.website.starter.config)
        self.repo = None
        self.gl = gitlab.Gitlab(
            url=settings.GIT_API_URL,
            private_token=get_token(),
            timeout=settings.GITLAB_TIMEOUT,
        )
        self.group = self.gl.groups.get(settings.GIT_ORGANIZATION)

    @property
    def repo_path(self) -> str:
        """Return the full path to the website repo under the configured group."""
        return f"{self.group.full_path}/{self.website.short_id}"

    @retry_on_failure
    def get_repo(self):
        """Get the website repo, create if necessary."""
        if not self.repo:
            try:
                self.repo = self.gl.projects.get(self.repo_path)
            except GitlabGetError as ge:
                if ge.response_code == 404:  # noqa: PLR2004
                    self.repo = self.create_repo()
                else:
                    raise
        return self.repo

    @retry_on_failure
    def repo_exists(self) -> bool:
        """Return True if the repo already exists."""
        try:
            self.gl.projects.get(self.repo_path)
        except GitlabGetError as ge:
            if ge.response_code == 404:  # noqa: PLR2004
                return False
            raise
        else:
            return True

    @retry_on_failure
    def create_repo(self, **kwargs):
        """Create a website repo."""
        try:
            self.repo = self.gl.projects.create(
                {
                    "name": self.website.short_id,
                    "namespace_id": self.group.id,
                    "initialize_with_readme": True,
                    "visibility": "public",
                    **kwargs,
                }
            )
        except GitlabCreateError as ge:
            if ge.response_code == 400:  # noqa: PLR2004
                self.repo = self.gl.projects.get(self.repo_path)
                log.debug("Repo already exists: %s", self.website.name)
            else:
                raise

        default_branch = self.repo.default_branch
        if default_branch != settings.GIT_BRANCH_MAIN:
            self.rename_branch(default_branch, settings.GIT_BRANCH_MAIN)
            self.repo.default_branch = settings.GIT_BRANCH_MAIN
            self.repo.save()

        existing_branches = [
            branch.name for branch in self.repo.branches.list(get_all=True)
        ]
        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            if branch not in existing_branches:
                self.create_branch(branch, settings.GIT_BRANCH_MAIN)

        return self.repo

    @retry_on_failure
    def create_branch(
        self,
        branch: str,
        source: str,
        *,
        delete_source: bool = False,
    ):
        """Create a new branch and optionally delete the source branch."""
        repo = self.get_repo()
        try:
            new_branch = repo.branches.create({"branch": branch, "ref": source})
        except GitlabCreateError as ge:
            if ge.response_code == 400:  # noqa: PLR2004
                new_branch = repo.branches.get(branch)
            else:
                raise

        if delete_source:
            try:
                repo.branches.delete(source)
            except GitlabDeleteError as ge:
                if ge.response_code != 404:  # noqa: PLR2004
                    raise
        return new_branch

    def rename_branch(self, from_name: str, to_name: str):
        """Rename a git branch by creating destination then deleting source."""
        return self.create_branch(to_name, from_name, delete_source=True)

    @retry_on_failure
    def upsert_content_file(self, website_content: WebsiteContent, **kwargs):
        """Create or update a file in git."""
        destination_filepath = get_destination_filepath(
            website_content, self.site_config
        )
        if not destination_filepath:
            return None

        repo = self.get_repo()
        data = serialize_content_to_file(
            site_config=self.site_config, website_content=website_content
        )
        git_user = self.git_user(website_content.updated_by)

        try:
            repo.files.get(file_path=destination_filepath, ref=settings.GIT_BRANCH_MAIN)
            action = "update"
        except GitlabGetError as ge:
            if ge.response_code == 404:  # noqa: PLR2004
                action = "create"
            else:
                raise

        return repo.commits.create(
            {
                "branch": settings.GIT_BRANCH_MAIN,
                "commit_message": f"{action.capitalize()} {destination_filepath}",
                "author_name": git_user["name"],
                "author_email": git_user["email"],
                "actions": [
                    {
                        "action": action,
                        "file_path": destination_filepath,
                        "content": data,
                        **kwargs,
                    }
                ],
            }
        )

    def upsert_content_files(
        self,
        query_set: WebsiteContentQuerySet | None = None,
        *,
        use_batch_commits: bool = False,
        batch_size: int | None = None,
    ):
        """Commit all website content, with 1 commit per user by default."""
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
            self.upsert_content_files_for_user(
                user_id,
                query_set,
                use_batch_commits=use_batch_commits,
                batch_size=batch_size,
            )

    @retry_on_failure
    def upsert_content_files_for_user(
        self,
        user_id=None,
        query_set: WebsiteContentQuerySet | None = None,
        *,
        use_batch_commits: bool = False,
        batch_size: int | None = None,
    ):
        """Upsert WebsiteContent objects to GitLab in one or more commits."""
        unsynced_states = ContentSyncState.objects.filter(
            Q(content__website=self.website) & Q(content__updated_by=user_id)
        ).exclude(
            Q(current_checksum=F("synced_checksum"), content__deleted__isnull=True)
            & Q(synced_checksum__isnull=False)
        )
        if query_set:
            unsynced_states = unsynced_states.filter(content__in=query_set)

        commit_batch_size = max(
            1,
            batch_size
            if batch_size is not None
            else getattr(settings, "GITLAB_COMMIT_BATCH_SIZE", 200),
        )
        user = User.objects.filter(id=user_id).first()
        pending_actions: list[dict[str, str]] = []
        pending_results: list[SyncResult] = []
        latest_commit = None

        for sync_state in unsynced_states.iterator():
            content = sync_state.content
            filepath = get_destination_filepath(content, self.site_config)
            if not filepath:
                continue

            current_checksum = content.calculate_checksum()
            if sync_state.current_checksum != current_checksum:
                sync_state.current_checksum = current_checksum
                sync_state.save()
                if (
                    current_checksum == sync_state.synced_checksum
                    and not content.deleted
                ):
                    continue

            data = serialize_content_to_file(
                site_config=self.site_config, website_content=content
            )
            actions = self.get_commit_actions(sync_state, data, filepath)
            if not actions:
                continue

            pending_results.append(
                SyncResult(
                    sync_id=sync_state.id,
                    filepath=filepath,
                    checksum=current_checksum,
                    deleted=content.deleted is not None,
                )
            )
            pending_actions.extend(actions)

            if use_batch_commits and len(pending_results) >= commit_batch_size:
                latest_commit = self.commit_actions(pending_actions, user)
                self.update_sync_states(pending_results)
                log.info(
                    "Committed GitLab sync batch for website=%s user_id=%s items=%d actions=%d",  # noqa: E501
                    self.website.name,
                    user_id,
                    len(pending_results),
                    len(pending_actions),
                )
                pending_actions = []
                pending_results = []

        if not pending_actions:
            return latest_commit

        latest_commit = self.commit_actions(pending_actions, user)
        self.update_sync_states(pending_results)
        if use_batch_commits:
            log.info(
                "Committed GitLab sync batch for website=%s user_id=%s items=%d actions=%d",  # noqa: E501
                self.website.name,
                user_id,
                len(pending_results),
                len(pending_actions),
            )
        return latest_commit

    def update_sync_states(self, synced_results: list[SyncResult]):
        """Persist sync-state updates for a committed batch."""
        if not synced_results:
            return None

        for sync_result in synced_results:
            sync_state = ContentSyncState.objects.get(id=sync_result.sync_id)
            if sync_result.deleted:
                sync_state.content.delete(force_policy=HARD_DELETE)
            else:
                sync_state.data = {GIT_DATA_FILEPATH: sync_result.filepath}
                sync_state.synced_checksum = sync_result.checksum
                sync_state.save()
        return True

    @retry_on_failure
    def delete_content_file(self, content: WebsiteContent):
        """Delete a file from git."""
        repo = self.get_repo()
        filepath = get_destination_filepath(content, self.site_config)
        git_user = self.git_user(content.updated_by)
        return repo.commits.create(
            {
                "branch": settings.GIT_BRANCH_MAIN,
                "commit_message": f"Delete {filepath}",
                "author_name": git_user["name"],
                "author_email": git_user["email"],
                "actions": [{"action": "delete", "file_path": filepath}],
            }
        )

    @retry_on_failure
    def merge_branches(self, from_branch: str, to_branch: str):
        """Merge one branch to another via merge request."""
        repo = self.get_repo()
        target_tip_before = repo.branches.get(to_branch).commit["id"]
        try:
            merge_request = repo.mergerequests.create(
                {
                    "source_branch": from_branch,
                    "target_branch": to_branch,
                    "title": f"Merge {from_branch} to {to_branch}",
                    "remove_source_branch": False,
                }
            )
        except GitlabCreateError as ge:
            if ge.response_code != 409:  # noqa: PLR2004
                raise
            existing_mrs = repo.mergerequests.list(
                state="opened",
                source_branch=from_branch,
                target_branch=to_branch,
                get_all=True,
            )
            if not existing_mrs:
                raise
            merge_request = repo.mergerequests.get(existing_mrs[0].iid)

        try:
            merge_request.merge()
        except (GitlabUpdateError, GitlabMRClosedError) as ge:
            # 405 can mean no changes/already merged. Validate branch movement below.
            if ge.response_code != 405:  # noqa: PLR2004
                raise

        target_tip_after = repo.branches.get(to_branch).commit["id"]
        if target_tip_after != target_tip_before:
            return merge_request

        compare_result = repo.repository_compare(to_branch, from_branch)
        if len(compare_result.get("commits", [])) == 0:
            return merge_request

        msg = (
            "GitLab merge did not update target branch "
            f"{from_branch}->{to_branch} for website={self.website.name}"
        )
        raise RuntimeError(msg)

    def git_user(self, user: User | None) -> dict[str, str]:
        """Return a name/email mapping to be used as committer metadata."""
        name = settings.GIT_DEFAULT_USER_NAME
        email = settings.GIT_DEFAULT_USER_EMAIL
        if user:
            if features.is_enabled(features.GIT_ANONYMOUS_COMMITS):
                name = f"user_{user.id}"
            else:
                name = user.name or user.username
                email = user.email
        return {"name": name, "email": email}

    def get_commit_actions(
        self, sync_state: ContentSyncState, data: str, filepath: str
    ) -> list[dict[str, str]]:
        """Return commit actions for a modified ContentSyncState."""
        repo = self.get_repo()
        actions: list[dict[str, str]] = []

        if sync_state.content.deleted is None:
            try:
                repo.files.get(file_path=filepath, ref=settings.GIT_BRANCH_MAIN)
                action = "update"
            except GitlabGetError as ge:
                if ge.response_code == 404:  # noqa: PLR2004
                    action = "create"
                else:
                    raise
            actions.append({"action": action, "file_path": filepath, "content": data})

        if sync_state.data is None:
            return actions

        old_path = sync_state.data.get(GIT_DATA_FILEPATH, None)
        if old_path and (
            sync_state.content.deleted is not None or old_path != filepath
        ):
            actions.append({"action": "delete", "file_path": old_path})

        return actions

    def commit_actions(self, actions: list[dict[str, str]], user: User | None):
        """Create a commit containing all actions in the main branch."""
        repo = self.get_repo()
        git_user = self.git_user(user)
        return repo.commits.create(
            {
                "branch": settings.GIT_BRANCH_MAIN,
                "commit_message": "Sync all content",
                "author_name": git_user["name"],
                "author_email": git_user["email"],
                "actions": actions,
            }
        )

    def get_all_file_paths(self, path: str) -> Iterable[str]:
        """Yield all file paths in the repo."""
        repo = self.get_repo()
        tree = repo.repository_tree(
            path=path,
            ref=settings.GIT_BRANCH_MAIN,
            recursive=True,
            get_all=True,
        )
        for item in tree:
            if item.get("type") == "blob" and item.get("path") != "README.md":
                yield item["path"]

    def batch_delete_files(self, paths: list[str], user: User | None = None):
        """Batch delete multiple git files in a single commit."""
        if not paths:
            return None
        actions = [{"action": "delete", "file_path": path} for path in paths]
        return self.commit_actions(actions, user)

    def get_rate_limit_status(self) -> tuple[int, int, datetime] | None:
        """Return GitLab API rate limit state if available."""
        self.get_repo()
        remaining = getattr(self.gl, "rate_limit_remaining", None)
        limit = getattr(self.gl, "rate_limit", None)
        reset = getattr(self.gl, "rate_limit_reset", None)
        if remaining is None or limit is None or reset is None:
            return None
        reset_time = datetime.fromtimestamp(reset, tz=UTC)
        return remaining, limit, reset_time
