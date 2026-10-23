"""GitLab API tests"""

from types import SimpleNamespace

import pytest
from gitlab.exceptions import (
    GitlabCreateError,
    GitlabDeleteError,
    GitlabMRClosedError,
)

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.apis.gitlab import GitlabApiWrapper, update_all_repos_visibility
from users.factories import UserFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.site_config_api import SiteConfig

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_retry_sleep(mocker):
    """Keep retry backoff out of the suite's wall-clock time.

    Two sleeps matter here and they are different imports: merge_branches
    waits on content_sync.apis.gitlab.sleep, while retry_on_failure waits on
    its own content_sync.decorators.sleep. Patching only the first left the
    tests that trigger a retry sleeping CONTENT_SYNC_RETRIES - 1 seconds each.
    """
    mocker.patch("content_sync.apis.gitlab.sleep")
    mocker.patch("content_sync.decorators.sleep")


def fake_destination_filepath(website_content, *args) -> str:
    """Return a deterministic filepath for a WebsiteContent record."""
    return f"path/to/{website_content.filename}.md"


@pytest.fixture
def gitlab_api_wrapper(settings, mocker):
    """Create a GitlabApiWrapper with a mocked GitLab client."""
    settings.GIT_TOKEN = "faketoken"  # noqa: S105
    settings.GIT_API_URL = "https://gitlab.example.com"
    settings.GIT_ORGANIZATION = "fake_group"
    settings.GITLAB_COMMIT_BATCH_SIZE = 2

    mock_gitlab_cls = mocker.patch("content_sync.apis.gitlab.gitlab.Gitlab")
    mock_gitlab_cls.return_value.groups.get.return_value = SimpleNamespace(
        id=1,
        full_path="fake_group",
    )

    website = WebsiteFactory.create()
    return GitlabApiWrapper(
        website=website,
        site_config=SiteConfig(website.starter.config),
    )


def test_upsert_content_files_for_user_chunked_commits(
    mocker,
    gitlab_api_wrapper,
):
    """upsert_content_files_for_user should split large syncs into multiple commits."""
    user = UserFactory.create()
    contents = WebsiteContentFactory.create_batch(
        3,
        website=gitlab_api_wrapper.website,
        updated_by=user,
    )

    mocker.patch(
        "content_sync.apis.gitlab.get_destination_filepath",
        side_effect=fake_destination_filepath,
    )
    mocker.patch(
        "content_sync.apis.gitlab.serialize_content_to_file",
        return_value="serialized-content",
    )
    mocker.patch.object(
        gitlab_api_wrapper,
        "get_commit_actions",
        side_effect=lambda _sync_state, data, filepath: [
            {
                "action": "create",
                "file_path": filepath,
                "content": data,
            }
        ],
    )
    commit_actions = mocker.patch.object(
        gitlab_api_wrapper,
        "commit_actions",
        side_effect=["commit-1", "commit-2"],
    )

    commit = gitlab_api_wrapper.upsert_content_files_for_user(
        user.id, use_batch_commits=True, batch_size=2
    )

    assert commit == "commit-2"
    assert commit_actions.call_count == 2
    assert len(commit_actions.call_args_list[0].args[0]) == 2
    assert len(commit_actions.call_args_list[1].args[0]) == 1

    for content in contents:
        content.refresh_from_db()
        assert content.content_sync_state.is_synced is True
        assert content.content_sync_state.data[GIT_DATA_FILEPATH] == (
            fake_destination_filepath(content)
        )


def test_upsert_content_files_for_user_defaults_to_single_commit(
    mocker,
    gitlab_api_wrapper,
):
    """upsert_content_files_for_user should use one commit by default."""
    user = UserFactory.create()
    WebsiteContentFactory.create_batch(
        3,
        website=gitlab_api_wrapper.website,
        updated_by=user,
    )

    mocker.patch(
        "content_sync.apis.gitlab.get_destination_filepath",
        side_effect=fake_destination_filepath,
    )
    mocker.patch(
        "content_sync.apis.gitlab.serialize_content_to_file",
        return_value="serialized-content",
    )
    mocker.patch.object(
        gitlab_api_wrapper,
        "get_commit_actions",
        side_effect=lambda _sync_state, data, filepath: [
            {
                "action": "create",
                "file_path": filepath,
                "content": data,
            }
        ],
    )
    commit_actions = mocker.patch.object(
        gitlab_api_wrapper,
        "commit_actions",
        return_value="commit-1",
    )

    commit = gitlab_api_wrapper.upsert_content_files_for_user(user.id)

    assert commit == "commit-1"
    assert commit_actions.call_count == 1
    assert len(commit_actions.call_args_list[0].args[0]) == 3


def test_merge_branches_reuses_existing_open_mr_on_409(mocker, gitlab_api_wrapper):
    """merge_branches should reuse an existing open MR when create returns 409."""
    existing_mr_stub = mocker.Mock()
    existing_mr_stub.iid = 123
    existing_mr = mocker.Mock()
    repo = mocker.Mock()
    repo.mergerequests.create.side_effect = GitlabCreateError(
        "conflict",
        response_code=409,
    )
    repo.mergerequests.list.return_value = [existing_mr_stub]
    repo.mergerequests.get.return_value = existing_mr

    preview_branch = mocker.Mock()
    preview_branch.commit = {"id": "sha-main"}
    repo.branches.get.return_value = preview_branch
    repo.repository_compare.return_value = {"commits": []}

    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    result = gitlab_api_wrapper.merge_branches("main", "preview")

    assert result is existing_mr
    repo.mergerequests.list.assert_called_once_with(
        state="opened",
        source_branch="main",
        target_branch="preview",
        get_all=True,
    )
    repo.mergerequests.get.assert_called_once_with(123)
    existing_mr.merge.assert_called_once()


def test_merge_branches_raises_on_409_without_existing_mr(mocker, gitlab_api_wrapper):
    """merge_branches should raise when create conflicts and no open MR is found."""
    repo = mocker.Mock()
    repo.mergerequests.create.side_effect = GitlabCreateError(
        "conflict",
        response_code=409,
    )
    repo.mergerequests.list.return_value = []

    same_branch = mocker.Mock()
    same_branch.commit = {"id": "sha-main"}
    repo.branches.get.return_value = same_branch

    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    with pytest.raises(GitlabCreateError):
        gitlab_api_wrapper.merge_branches("main", "preview")


def test_merge_branches_raises_when_target_tip_does_not_change(
    mocker, gitlab_api_wrapper
):
    """merge_branches should fail if a merge attempt does not advance target."""
    mr = mocker.Mock()
    repo = mocker.Mock()
    repo.mergerequests.create.return_value = mr

    preview_branch = mocker.Mock()
    preview_branch.commit = {"id": "preview-sha"}
    repo.branches.get.return_value = preview_branch
    repo.repository_compare.return_value = {"commits": [{"id": "main-sha"}]}
    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    with pytest.raises(RuntimeError):
        gitlab_api_wrapper.merge_branches("main", "preview")


def test_merge_branches_accepts_noop_when_already_up_to_date(
    mocker, gitlab_api_wrapper
):
    """merge_branches should treat already-equal source/target tips as a no-op."""
    mr = mocker.Mock()
    repo = mocker.Mock()
    repo.mergerequests.create.return_value = mr

    branch_preview = mocker.Mock()
    branch_preview.commit = {"id": "same-sha"}
    repo.branches.get.return_value = branch_preview
    repo.repository_compare.return_value = {"commits": []}
    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    result = gitlab_api_wrapper.merge_branches("main", "preview")

    assert result is mr


def test_merge_branches_accepts_mr_closed_when_already_up_to_date(
    mocker, gitlab_api_wrapper
):
    """merge_branches should allow MR closed errors when tips already match."""
    mr = mocker.Mock()
    mr.iid = 13
    mr.merge.side_effect = GitlabMRClosedError("closed", response_code=405)
    refreshed_mr = mocker.Mock()
    refreshed_mr.state = "closed"
    repo = mocker.Mock()
    repo.mergerequests.create.return_value = mr
    repo.mergerequests.get.return_value = refreshed_mr

    preview_branch = mocker.Mock()
    preview_branch.commit = {"id": "same-sha"}
    repo.branches.get.return_value = preview_branch
    repo.repository_compare.return_value = {"commits": []}

    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    result = gitlab_api_wrapper.merge_branches("main", "preview")

    assert result is mr


def test_merge_branches_retries_once_after_405(mocker, gitlab_api_wrapper):
    """merge_branches should refresh and retry merge once on transient 405."""
    mr = mocker.Mock()
    mr.iid = 7
    mr.merge.side_effect = GitlabMRClosedError("closed", response_code=405)
    refreshed_mr = mocker.Mock()
    refreshed_mr.state = "opened"
    refreshed_mr.merge.return_value = None

    repo = mocker.Mock()
    repo.mergerequests.create.return_value = mr
    repo.mergerequests.get.return_value = refreshed_mr

    before = mocker.Mock()
    before.commit = {"id": "old-sha"}
    still_before = mocker.Mock()
    still_before.commit = {"id": "old-sha"}
    after = mocker.Mock()
    after.commit = {"id": "new-sha"}
    repo.branches.get.side_effect = [before, still_before, after]
    repo.repository_compare.side_effect = [
        {"commits": [{"id": "from-sha"}]},
        {"commits": []},
    ]

    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    result = gitlab_api_wrapper.merge_branches("main", "preview")

    assert result is refreshed_mr
    mr.merge.assert_called_once()
    refreshed_mr.merge.assert_called_once()
    repo.mergerequests.get.assert_called_once_with(7)


def test_create_repo_sets_public_visibility(settings, mocker):
    """create_repo should create the project with visibility='public'."""
    settings.GIT_TOKEN = "faketoken"  # noqa: S105
    settings.GIT_API_URL = "https://gitlab.example.com"
    settings.GIT_ORGANIZATION = "fake_group"
    settings.GITLAB_TIMEOUT = None

    mock_gitlab_cls = mocker.patch("content_sync.apis.gitlab.gitlab.Gitlab")
    mock_gl = mock_gitlab_cls.return_value
    mock_group = SimpleNamespace(id=1, full_path="fake_group")
    mock_gl.groups.get.return_value = mock_group

    fake_repo = mocker.Mock()
    fake_repo.default_branch = "main"
    fake_repo.branches.list.return_value = []
    mock_gl.projects.create.return_value = fake_repo

    website = WebsiteFactory.create()
    wrapper = GitlabApiWrapper(
        website=website, site_config=SiteConfig(website.starter.config)
    )
    wrapper.create_repo()

    create_call_kwargs = mock_gl.projects.create.call_args[0][0]
    assert create_call_kwargs["visibility"] == "public"


def test_update_all_repos_visibility(settings, mocker):
    """update_all_repos_visibility should set visibility on repos that differ."""
    settings.GIT_TOKEN = "faketoken"  # noqa: S105
    settings.GIT_API_URL = "https://gitlab.example.com"
    settings.GIT_ORGANIZATION = "fake_group"
    settings.GITLAB_TIMEOUT = None

    mock_gitlab_cls = mocker.patch("content_sync.apis.gitlab.gitlab.Gitlab")
    mock_gl = mock_gitlab_cls.return_value
    mock_group = mocker.Mock()

    private_project_stub = mocker.Mock()
    private_project_stub.id = 1
    public_project_stub = mocker.Mock()
    public_project_stub.id = 2

    mock_group.projects.list.side_effect = [
        [private_project_stub, public_project_stub],
        [],
    ]
    mock_gl.groups.get.return_value = mock_group

    private_project = mocker.Mock()
    private_project.visibility = "private"
    public_project = mocker.Mock()
    public_project.visibility = "public"

    mock_gl.projects.get.side_effect = [private_project, public_project]

    count = update_all_repos_visibility(visibility="public")

    assert count == 1
    assert private_project.visibility == "public"
    private_project.save.assert_called_once()
    public_project.save.assert_not_called()


def test_rename_branch_switches_the_default_before_deleting(mocker, gitlab_api_wrapper):
    """GitLab refuses to delete whichever branch a project points at."""
    events = []
    repo = mocker.Mock()
    repo.default_branch = "master"
    repo.branches.create.side_effect = lambda payload: events.append(
        f"create:{payload['branch']}"
    )
    repo.save.side_effect = lambda: events.append(f"save:{repo.default_branch}")
    repo.branches.delete.side_effect = lambda branch: events.append(f"delete:{branch}")
    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    gitlab_api_wrapper.rename_branch("master", "main")

    assert events == ["create:main", "save:main", "delete:master"]


def test_rename_branch_leaves_an_unrelated_default_alone(mocker, gitlab_api_wrapper):
    """Renaming a branch that is not the default must not move the default."""
    repo = mocker.Mock()
    repo.default_branch = "main"
    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    gitlab_api_wrapper.rename_branch("topic", "feature")

    repo.save.assert_not_called()
    assert repo.default_branch == "main"
    repo.branches.delete.assert_called_once_with("topic")


def test_create_repo_renames_a_non_main_default_branch(settings, mocker):
    """An instance defaulting to master must still end up on GIT_BRANCH_MAIN."""
    settings.GIT_TOKEN = "faketoken"  # noqa: S105
    settings.GIT_API_URL = "https://gitlab.example.com"
    settings.GIT_ORGANIZATION = "fake_group"
    settings.GITLAB_TIMEOUT = None

    mock_gitlab_cls = mocker.patch("content_sync.apis.gitlab.gitlab.Gitlab")
    mock_gl = mock_gitlab_cls.return_value
    mock_gl.groups.get.return_value = SimpleNamespace(id=1, full_path="fake_group")

    fake_repo = mocker.Mock()
    fake_repo.default_branch = "master"
    fake_repo.branches.list.return_value = []
    mock_gl.projects.create.return_value = fake_repo

    website = WebsiteFactory.create()
    wrapper = GitlabApiWrapper(
        website=website, site_config=SiteConfig(website.starter.config)
    )
    wrapper.create_repo()

    assert fake_repo.default_branch == settings.GIT_BRANCH_MAIN
    fake_repo.save.assert_called_once()
    fake_repo.branches.delete.assert_called_once_with("master")


def test_delete_branch_retries_a_transient_failure(mocker, gitlab_api_wrapper):
    """A transient delete failure must not strand the old default branch."""
    repo = mocker.Mock()
    repo.branches.delete.side_effect = [
        GitlabDeleteError("boom", response_code=500),
        None,
    ]
    mocker.patch.object(gitlab_api_wrapper, "get_repo", return_value=repo)

    gitlab_api_wrapper.delete_branch("master")

    assert repo.branches.delete.call_count == 2


def test_upsert_re_reads_the_tree_after_a_failed_commit(mocker, gitlab_api_wrapper):
    """A commit GitLab applied before failing must not retry as a create."""
    user = UserFactory.create()
    content = WebsiteContentFactory.create(
        website=gitlab_api_wrapper.website, updated_by=user
    )
    filepath = fake_destination_filepath(content)

    mocker.patch(
        "content_sync.apis.gitlab.get_destination_filepath",
        side_effect=fake_destination_filepath,
    )
    mocker.patch(
        "content_sync.apis.gitlab.serialize_content_to_file",
        return_value="serialized-content",
    )
    # Empty on the first read; the failed commit landed anyway, so the second
    # read -- which only happens if the cache was dropped -- finds the file.
    paths = mocker.patch.object(
        gitlab_api_wrapper,
        "get_all_file_paths",
        side_effect=[iter([]), iter([filepath])],
    )
    commit_actions = mocker.patch.object(
        gitlab_api_wrapper,
        "commit_actions",
        side_effect=[GitlabCreateError("timed out", response_code=504), "commit-1"],
    )

    gitlab_api_wrapper.upsert_content_files_for_user(user.id)

    assert paths.call_count == 2
    assert commit_actions.call_count == 2
    first = commit_actions.call_args_list[0].args[0]
    second = commit_actions.call_args_list[1].args[0]
    assert [action["action"] for action in first] == ["create"]
    assert [action["action"] for action in second] == ["update"]
    content.refresh_from_db()
    assert content.content_sync_state.is_synced is True
