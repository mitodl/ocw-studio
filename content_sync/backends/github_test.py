"""github backend tests"""

from base64 import b64encode
from types import SimpleNamespace

import pytest
from github.GithubObject import NotSet

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.backends.github import GithubBackend
from content_sync.models import ContentSyncState
from content_sync.utils import get_destination_filepath
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig

pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@pytest.fixture()
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


@pytest.fixture()
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


def test_sync_all_content_to_backend(github):
    """Test that sync_all_content_to_backend makes the appropriate api call"""
    github.backend.sync_all_content_to_backend()
    github.api.upsert_content_files.assert_called_once()


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


@pytest.mark.parametrize("ref", [NotSet, "abc123jfkdjfdkfj"])
@pytest.mark.parametrize("path", [None, "src/syllabus_test_sync.md"])
def test_sync_all_content_to_db(mocker, github, patched_file_deserialize, ref, path):
    """Test that sync_all_content_to_db iterates over all repo content"""
    fake_dir = mocker.Mock(type="dir", path="src", content="")
    fake_files = [
        mocker.Mock(type="file", path=path, content=b64encode(content.encode("utf-8")))
        for (path, content) in [
            [
                "src/__index_test_sync.md",
                "---\nuid: 1\nlayout: course_section\n---\nfile 1 content",
            ],
            [
                "src/syllabus_test_sync.md",
                "---\nuid: 2\nlayout: course_section\n---\nfile 2 content",
            ],
            [
                "README.md",
                "# Read Me",
            ],
        ]
    ]
    # Two actual content files to sync. README.md should be ignored.
    expected_sync_count = 2 if not path else 1
    github.api.get_repo.return_value.get_contents.side_effect = [
        [fake_dir],
        fake_files,
    ]
    website_contents = github.backend.website.websitecontent_set.all()
    patched_file_deserialize.side_effect = website_contents

    if ref is NotSet:
        github.backend.sync_all_content_to_db(path=path)
    else:
        github.backend.sync_all_content_to_db(ref=ref, path=path)
    assert patched_file_deserialize.call_count == expected_sync_count
    patched_file_deserialize.assert_any_call(
        site_config=mocker.ANY,
        website=github.backend.website,
        filepath="src/syllabus_test_sync.md",
        file_contents=mocker.ANY,
    )
    assert all(
        sync_state.is_synced is (ref is NotSet)
        for sync_state in ContentSyncState.objects.filter(
            content__in=website_contents[0:expected_sync_count]
        )
    )
    assert github.backend.website.websitecontent_set.count() == (
        2 if ref is NotSet and not path else 5
    )


def test_delete_orphaned_content_in_backend(github):
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
    github.backend.delete_orphaned_content_in_backend()
    github.api.get_all_file_paths.assert_called_once()
    github.api.batch_delete_files.assert_called_once_with([*paths_to_delete])
