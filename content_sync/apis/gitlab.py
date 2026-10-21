"""GitLab API wrapper"""

import logging
from base64 import b64decode
from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from collections.abc import Iterable

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


# Last-seen rate limit headers, per process.
_RATE_LIMIT_STATE: dict[str, int] = {}


def _record_rate_limit(response, *_args, **_kwargs):
    """Stash GitLab's RateLimit-* headers on the session for later reads.

    python-gitlab exposes no rate-limit state of its own (checked against
    6.5.0: the client has no such attributes), so the only way to honour
    GITLAB_RATE_LIMIT_* is to read the headers GitLab returns on every
    response. Self-managed instances often omit them, hence the None guard in
    get_rate_limit_status.
    """
    headers = response.headers
    remaining = headers.get("RateLimit-Remaining")
    limit = headers.get("RateLimit-Limit")
    reset = headers.get("RateLimit-Reset")
    if remaining is None or limit is None or reset is None:
        return response
    _RATE_LIMIT_STATE["remaining"] = int(remaining)
    _RATE_LIMIT_STATE["limit"] = int(limit)
    _RATE_LIMIT_STATE["reset"] = int(reset)
    return response


def _gitlab_client() -> gitlab.Gitlab:
    """Build a GitLab client that trusts our configured URL.

    keep_base_url stops python-gitlab following next-page links that point
    somewhere other than the URL we configured, which a GitLab behind a
    TLS-terminating proxy will happily advertise.

    It is not a cure for every bad external_url. python-gitlab only rewrites a
    next-page URL that does not already start with the configured one, so an
    instance advertising `https://host:80` still hands back links we follow
    into a failed handshake. That instance needs its external_url corrected.
    """
    client = gitlab.Gitlab(
        url=settings.GIT_API_URL,
        private_token=get_token(),
        timeout=settings.GITLAB_TIMEOUT,
        keep_base_url=True,
    )
    client.session.hooks["response"].append(_record_rate_limit)
    return client


def update_all_repos_visibility(visibility: str = "public") -> int:
    """Update visibility for all repos in the configured GitLab group.

    Returns the number of repos updated.
    """
    gl = _gitlab_client()
    group = gl.groups.get(settings.GIT_ORGANIZATION)
    count = 0

    # The listing already carries `visibility`, so only repos actually being
    # changed need to be fetched in full. get_all=True is safe here because
    # _gitlab_client pins the base URL; without that pin python-gitlab follows
    # whatever next-link the server advertises, which is wrong on any GitLab
    # whose external_url is misconfigured.
    for stub in group.projects.list(get_all=True, per_page=100):
        if getattr(stub, "visibility", None) == visibility:
            continue
        project = gl.projects.get(stub.id)
        if project.visibility != visibility:
            project.visibility = visibility
            project.save()
            count += 1

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
        self.gl = _gitlab_client()
        self._group = None
        self._existing_path_cache = None
        self._pending_created: set[str] = set()

    @property
    def group(self):
        """The configured GitLab group, resolved on first use.

        Deliberately lazy: this is a network round trip, and a wrapper is
        constructed per website and per content operation, most of which never
        need the group at all.
        """
        if self._group is None:
            self._group = self.gl.groups.get(settings.GIT_ORGANIZATION)
        return self._group

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
            self.delete_branch(source)
        return new_branch

    def delete_branch(self, branch: str):
        """Delete a branch, tolerating one that is already gone."""
        try:
            self.get_repo().branches.delete(branch)
        except GitlabDeleteError as ge:
            if ge.response_code != 404:  # noqa: PLR2004
                raise

    def rename_branch(self, from_name: str, to_name: str):
        """Rename a git branch by creating destination then deleting source.

        GitLab refuses to delete whichever branch a project currently points
        at: the API answers 400 "The default branch of a project cannot be
        deleted". Renaming the default therefore has to move that pointer
        across before the old branch goes, or repo creation fails on every
        instance whose default_branch_name is not GIT_BRANCH_MAIN -- and
        fails identically on each retry.
        """
        repo = self.get_repo()
        new_branch = self.create_branch(to_name, from_name)
        if repo.default_branch == from_name:
            repo.default_branch = to_name
            repo.save()
        self.delete_branch(from_name)
        return new_branch

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
        # retry_on_failure re-enters this method, so start from what the repo
        # is actually known to hold rather than what a failed attempt staged.
        self._pending_created.clear()
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
                self._confirm_pending_paths()
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
        self._confirm_pending_paths()
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

    def _confirm_pending_paths(self):
        """Fold a committed batch's new paths into the existing-path cache."""
        if self._existing_path_cache is not None:
            self._existing_path_cache |= self._pending_created
        self._pending_created.clear()

    def update_sync_states(self, synced_results: list[SyncResult]):
        """Persist sync-state updates for a committed batch."""
        if not synced_results:
            return None

        # One query for the batch rather than one per result.
        states = ContentSyncState.objects.filter(
            id__in=[result.sync_id for result in synced_results]
        ).select_related("content")
        by_id = {state.id: state for state in states}

        to_update = []
        for sync_result in synced_results:
            sync_state = by_id.get(sync_result.sync_id)
            if sync_state is None:
                continue
            if sync_result.deleted:
                sync_state.content.delete(force_policy=HARD_DELETE)
            else:
                sync_state.data = {GIT_DATA_FILEPATH: sync_result.filepath}
                sync_state.synced_checksum = sync_result.checksum
                to_update.append(sync_state)
        if to_update:
            ContentSyncState.objects.bulk_update(to_update, ["data", "synced_checksum"])
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

    def _branch_tip(self, repo, branch: str) -> str | None:
        """Return a branch's tip commit id, or None if the branch is absent."""
        try:
            return repo.branches.get(branch).commit["id"]
        except GitlabGetError as ge:
            if ge.response_code == 404:  # noqa: PLR2004
                return None
            raise

    def _open_merge_request(self, repo, from_branch: str, to_branch: str):
        """Open a merge request, reusing the existing one if GitLab has it.

        A 409 here means an open merge request for this exact branch pair
        already exists, which is the normal case for a site published more
        than once.
        """
        try:
            return repo.mergerequests.create(
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
            return repo.mergerequests.get(existing_mrs[0].iid)

    @retry_on_failure
    def merge_branches(self, from_branch: str, to_branch: str):
        """Merge one branch to another via merge request."""
        repo = self.get_repo()
        target_tip_before = self._branch_tip(repo, to_branch)
        if target_tip_before is None:
            # The target branch does not exist yet. create_repo makes all
            # three, but a repo created before this layout -- or one where the
            # branch was deleted -- would otherwise fail every live publish
            # with an opaque "404 Branch Not Found". Branching from the source
            # produces exactly the state a merge would have left behind.
            log.info(
                "Creating missing branch %s from %s for %s",
                to_branch,
                from_branch,
                self.website.name,
            )
            return self.create_branch(to_branch, from_branch)
        merge_request = self._open_merge_request(repo, from_branch, to_branch)

        for _ in range(3):
            try:
                merge_request.merge()
            except (GitlabUpdateError, GitlabMRClosedError) as ge:
                if ge.response_code != 405:  # noqa: PLR2004
                    raise

            target_tip_after = self._branch_tip(repo, to_branch)
            if target_tip_after != target_tip_before:
                return merge_request

            compare_result = repo.repository_compare(to_branch, from_branch)
            if len(compare_result.get("commits", [])) == 0:
                return merge_request

            # GitLab can briefly report non-mergeable states right after MR
            # creation, so give it a moment before asking again; retrying with
            # no delay just burns the attempts inside the same window.
            sleep(settings.GITLAB_MERGE_RETRY_SLEEP)
            merge_request = repo.mergerequests.get(merge_request.iid)
            if getattr(merge_request, "state", "") != "opened":
                break

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

    def _existing_paths(self) -> set[str]:
        """Paths currently on the main branch, fetched once per wrapper.

        Replaces a files.get() per item when deciding create-vs-update: that
        put one API round trip in front of every file in a batch, so a
        200-file commit cost 200 extra requests before it could be made.
        """
        if self._existing_path_cache is None:
            self._existing_path_cache = set(self.get_all_file_paths(""))
        return self._existing_path_cache

    def get_commit_actions(
        self, sync_state: ContentSyncState, data: str, filepath: str
    ) -> list[dict[str, str]]:
        """Return commit actions for a modified ContentSyncState."""
        actions: list[dict[str, str]] = []

        if sync_state.content.deleted is None:
            known = (
                filepath in self._existing_paths() or filepath in self._pending_created
            )
            actions.append(
                {
                    "action": "update" if known else "create",
                    "file_path": filepath,
                    "content": data,
                }
            )
            # Held aside rather than folded into the cache: the commit carrying
            # this path can still fail, and a retry that believed the path
            # existed would send "update" for a file GitLab has never seen,
            # which it rejects -- so the retry could never succeed.
            self._pending_created.add(filepath)

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
        # per_page raises the page size from python-gitlab's default of 20 to
        # GitLab's maximum. Every publish syncs ocw-www first, so this listing
        # runs against the largest site we have: at RC size it was the
        # difference between 281 requests and 57.
        tree = repo.repository_tree(
            path=path,
            ref=settings.GIT_BRANCH_MAIN,
            recursive=True,
            get_all=True,
            per_page=100,
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
        """Return GitLab API rate limit state if available.

        Reads what the last response reported. Returns None when the instance
        sends no RateLimit-* headers, which is the common case for
        self-managed GitLab; the caller then falls back to a fixed delay.

        Deliberately does not touch the repo: this used to call get_repo(),
        which creates the project when it 404s, so asking for rate-limit
        status could create a repository.
        """
        remaining = _RATE_LIMIT_STATE.get("remaining")
        limit = _RATE_LIMIT_STATE.get("limit")
        reset = _RATE_LIMIT_STATE.get("reset")
        if remaining is None or limit is None or reset is None:
            return None
        return remaining, limit, datetime.fromtimestamp(reset, tz=UTC)
