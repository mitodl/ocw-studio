""" github backend tests """
from base64 import b64encode
from types import SimpleNamespace

import pytest

from content_sync.backends.github import GithubBackend
from content_sync.models import ContentSyncState
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@pytest.fixture
def github(settings, mocker, mock_branches):
    """ Create a github backend for a website """
    settings.GIT_TOKEN = "faketoken"
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
    yield SimpleNamespace(
        backend=backend, api=mock_github_api, repo=mock_repo, branches=mock_branches
    )


@pytest.fixture
def patched_file_serialize(mocker):
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
    """ Test that the create_website_in_backend function completes without errors and calls expected api functions"""
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


def test_create_backend_preview(settings, github):
    """Test that create_backend_preview makes the appropriate api merge call"""
    github.backend.create_backend_preview()
    github.api.upsert_content_files.assert_called_once()
    github.api.merge_branches.assert_called_once_with(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
    )


def test_create_backend_release(settings, github):
    """Test that create_backend_release makes the appropriate api merge calls"""
    github.backend.create_backend_release()
    github.api.merge_branches.assert_any_call(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
    )
    github.api.merge_branches.assert_any_call(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_RELEASE
    )


def test_create_content_in_db(github, github_content_file, patched_file_serialize):
    """Test that create_content_in_db makes the appropriate api call"""
    github.backend.create_content_in_db(github_content_file.obj)
    patched_file_serialize.assert_called_once_with(
        site_config=github.backend.site_config,
        website=github.backend.website,
        filepath=github_content_file.path,
        file_contents=github_content_file.content_str,
    )


def test_update_content_in_db(github, github_content_file, patched_file_serialize):
    """Test that update_content_in_db makes the appropriate api call"""
    github.backend.update_content_in_db(github_content_file.obj)
    patched_file_serialize.assert_called_once_with(
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


def test_sync_all_content_to_db(mocker, github, patched_file_serialize):
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
    expected_sync_count = 2
    github.api.get_repo.return_value.get_contents.side_effect = [
        [fake_dir],
        fake_files,
    ]
    website_contents = github.backend.website.websitecontent_set.all()
    patched_file_serialize.side_effect = website_contents

    github.backend.sync_all_content_to_db()
    assert patched_file_serialize.call_count == expected_sync_count
    assert all(
        [
            sync_state.is_synced
            for sync_state in ContentSyncState.objects.filter(
                content__in=website_contents[0:expected_sync_count]
            )
        ]
    )
