"""github backend tests"""

from base64 import b64encode
from types import SimpleNamespace

import pytest
from github.GithubObject import NotSet

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.backends.github import GithubBackend
from content_sync.models import ContentSyncState
from content_sync.utils import get_destination_filepath
from users.factories import UserFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig

pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@pytest.fixture
def github(settings, mocker, mock_branches):
    """Create a github backend for a website"""
    settings.GIT_TOKEN = "faketoken"  # noqa: S105
    settings.GIT_ORGANIZATION = "fake_org"
    mock_github_api = mocker.patch(
        "content_sync.backends.github.GithubApiWrapper",
    )
    mock_repo = mock_github_api.get_repo.return_value
    mock_repo.default_branch = settings.GIT_BRANCH_MAIN
    mock_repo.get_branches.return_value = [mock_branches[0]]

    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(5, website=website)
    backend = GithubBackend(website)
    backend.api = mock_github_api
    return SimpleNamespace(
        backend=backend, api=mock_github_api, repo=mock_repo, branches=mock_branches
    )


@pytest.fixture
def patched_file_deserialize(mocker):
    """Patches function that deserializes file contents to website content"""
    return mocker.patch(
        "content_sync.backends.github.deserialize_file_to_website_content"
    )


@pytest.mark.parametrize("exists", [True, False])
def test_backend_exists(github, exists):
    """backend_exists should return the expected boolean value"""
    github.api.repo_exists.return_value = exists
    assert github.backend.backend_exists() is exists


def test_create_website_in_backend(github):
    """Test that the create_website_in_backend function completes without errors and calls expected api functions"""
    github.backend.create_website_in_backend()
    github.api.create_repo.assert_called_once()


def test_create_content_in_backend(github):
    """Test that create_content_in_backend calls the appropriate api wrapper function and args"""
    content = github.backend.website.websitecontent_set.all().last()
    content_sync_state = content.content_sync_state
    initial_sha = content_sync_state.current_checksum
    assert initial_sha != content_sync_state.synced_checksum
    github.backend.create_content_in_backend(content.content_sync_state)
    github.api.upsert_content_file.assert_called_once_with(content)
    updated_sync = ContentSyncState.objects.get(id=content_sync_state.id)
    assert updated_sync.current_checksum == updated_sync.synced_checksum


def test_update_content_in_backend(github):
    """Test that update_content_in_backend calls the appropriate api wrapper function and args"""
    content = github.backend.website.websitecontent_set.all().last()
    github.backend.update_content_in_backend(content.content_sync_state)
    github.api.upsert_content_file.assert_called_once_with(content)


def test_abort_on_synced_checksum(github):
    """Test that creating/updating content does nothing if checksums match"""
    content = github.backend.website.websitecontent_set.all().last()
    content_sync_state = content.content_sync_state
    content_sync_state.synced_checksum = content_sync_state.current_checksum
    content_sync_state.save()
    github.backend.create_content_in_backend(content.content_sync_state)
    github.backend.update_content_in_backend(content.content_sync_state)
    github.api.upsert_content_file.assert_not_called()


def test_delete_content_in_backend(github):
    """Test that delete_content_in_backend makes the appropriate api call"""
    content = github.backend.website.websitecontent_set.all().last()
    content_sync_state = content.content_sync_state
    github.backend.delete_content_in_backend(content_sync_state)
    github.api.delete_content_file.assert_called_once_with(content)
    assert ContentSyncState.objects.filter(id=content_sync_state.id).first() is None
    assert WebsiteContent.objects.filter(id=content.id).first() is None


@pytest.mark.parametrize("override_user", [True, False])
def test_sync_all_content_to_backend(github, override_user):
    """Test that sync_all_content_to_backend makes the appropriate api call"""
    user = UserFactory.create() if override_user else None
    github.backend.sync_all_content_to_backend(commit_user=user)
    github.api.upsert_content_files.assert_called_once_with(
        query_set=None, commit_user=user
    )


def test_create_backend_draft(settings, github):
    """Test that merge_backend_draft makes the appropriate api merge call"""
    github.backend.merge_backend_draft()
    github.api.upsert_content_files.assert_called_once()
    github.api.merge_branches.assert_called_once_with(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
    )


def test_create_backend_live(settings, github):
    """Test that merge_backend_live makes the appropriate api merge calls"""
    github.backend.merge_backend_live()
    github.api.merge_branches.assert_any_call(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
    )
    github.api.merge_branches.assert_any_call(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_RELEASE
    )


def test_create_content_in_db(github, github_content_file, patched_file_deserialize):
    """Test that create_content_in_db makes the appropriate api call"""
    github.backend.create_content_in_db(github_content_file.obj)
    patched_file_deserialize.assert_called_once_with(
        site_config=github.backend.site_config,
        website=github.backend.website,
        filepath=github_content_file.path,
        file_contents=github_content_file.content_str,
    )


def test_update_content_in_db(github, github_content_file, patched_file_deserialize):
    """Test that update_content_in_db makes the appropriate api call"""
    github.backend.update_content_in_db(github_content_file.obj)
    patched_file_deserialize.assert_called_once_with(
        site_config=github.backend.site_config,
        website=github.backend.website,
        filepath=github_content_file.path,
        file_contents=github_content_file.content_str,
    )


def test_delete_content_in_db(github):
    """Test that delete_content_in_db makes the appropriate api call"""
    sync_state = github.backend.website.websitecontent_set.first().content_sync_state
    github.backend.delete_content_in_db(sync_state)
    assert ContentSyncState.objects.filter(id=sync_state.id).first() is None
    assert WebsiteContent.objects.filter(id=sync_state.content.id).first() is None


@pytest.mark.parametrize("ref", [None, "abc123"])
@pytest.mark.parametrize(
    ("path", "expected_paths"),
    [
        (None, ["src/syllabus.md", "src-old/notes.md", "src/units/week-1.md"]),
        ("src", ["src/syllabus.md", "src/units/week-1.md"]),
        ("src/", ["src/syllabus.md", "src/units/week-1.md"]),
        ("src/syllabus.md", ["src/syllabus.md"]),
    ],
)
def test_sync_all_content_to_db(
    github, patched_file_deserialize, ref, path, expected_paths
):
    """Import only the selected files and return their content IDs."""
    website_contents = github.backend.website.websitecontent_set.all()
    contents_by_path = dict(
        zip(
            ["src/syllabus.md", "src/units/week-1.md", "src-old/notes.md"],
            website_contents[:3],
            strict=True,
        )
    )
    syllabus, lesson, unrelated = (
        SimpleNamespace(type="file", path=filepath, content=b64encode(b"body"))
        for filepath in contents_by_path
    )
    repo_contents = {
        "": [
            SimpleNamespace(type="dir", path="src"),
            SimpleNamespace(type="dir", path="src-old"),
            SimpleNamespace(type="file", path="README.md"),
        ],
        "src": [syllabus, SimpleNamespace(type="dir", path="src/units")],
        "src/units": [lesson],
        "src-old": [unrelated],
        syllabus.path: syllabus,
    }
    github.repo.get_contents.side_effect = lambda path, **_kwargs: repo_contents[path]
    patched_file_deserialize.side_effect = lambda filepath, **_kwargs: contents_by_path[
        filepath
    ]

    imported_ids = github.backend.sync_all_content_to_db(ref=ref, path=path)

    assert imported_ids == [
        contents_by_path[filepath].pk for filepath in expected_paths
    ]
    assert [
        call.kwargs["filepath"] for call in patched_file_deserialize.call_args_list
    ] == expected_paths
    github_ref = NotSet if ref is None else ref
    expected_repo_path = (path or "").rstrip("/")
    assert github.repo.get_contents.call_args_list[0].args == (expected_repo_path,)
    assert all(
        call.kwargs["ref"] == github_ref
        for call in github.repo.get_contents.call_args_list
    )
    assert all(
        sync_state.is_synced is (ref is None and sync_state.content_id in imported_ids)
        for sync_state in ContentSyncState.objects.filter(content__in=website_contents)
    )
    assert website_contents.count() == (
        len(expected_paths) if ref is None and path is None else 5
    )


@pytest.mark.parametrize("override_user", [True, False])
def test_delete_orphaned_content_in_backend(github, override_user):
    """delete_orphaned_content_in_backend should call batch_delete_files with correct paths"""
    prior_path = "content/old/pages/1.md"
    content = github.backend.website.websitecontent_set.all()
    ContentSyncState.objects.filter(content=content[2]).update(
        data={GIT_DATA_FILEPATH: prior_path}
    )
    paths_to_delete = ["content/nomatch/1.md", "content/nomatch/2.md"]
    github.api.site_config = SiteConfig(github.backend.website.starter.config)
    github.api.get_all_file_paths.return_value = iter(
        [
            get_destination_filepath(content[0], github.backend.api.site_config),
            get_destination_filepath(content[1], github.backend.api.site_config),
            prior_path,
            *paths_to_delete,
        ]
    )
    user = UserFactory.create() if override_user else None
    github.backend.delete_orphaned_content_in_backend(commit_user=user)
    github.api.get_all_file_paths.assert_called_once()
    github.api.batch_delete_files.assert_called_once_with([*paths_to_delete], user=user)
