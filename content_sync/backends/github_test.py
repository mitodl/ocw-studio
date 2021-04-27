""" github backend tests """
from base64 import b64decode, b64encode
from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from github import GithubException

from content_sync.backends.github import GithubBackend
from content_sync.models import ContentSyncState
from ocw_import.api import convert_data_to_content
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


def test_create_backend_new(settings, github):
    """ Test that the create_backend function completes without errors and calls expected api functions"""
    new_repo = github.backend.create_website_in_backend()
    github.repo.rename_branch.assert_not_called()
    github.api.create_branch.assert_any_call(
        settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_MAIN
    )
    github.api.create_branch.assert_any_call(
        settings.GIT_BRANCH_RELEASE, settings.GIT_BRANCH_MAIN
    )
    assert new_repo == github.api.get_repo()


def test_create_backend_again(mocker, github):
    """ Test that the create_backend function will try retrieving a repo if api.create_repo fails"""
    mock_log = mocker.patch("content_sync.backends.github.log.debug")
    github.api.create_repo.side_effect = GithubException(status=422, data={})
    new_repo = github.backend.create_website_in_backend()
    assert new_repo is not None
    assert github.api.get_repo.call_count == 2
    mock_log.assert_called_once_with(
        "Repo already exists: %s", github.backend.website.name
    )


def test_create_backend_custom_default_branch(settings, github):
    """ Test that the create_backend function creates a custom default branch name """
    settings.GIT_BRANCH_MAIN = "testing"
    github.repo.default_branch = "main"
    new_repo = github.backend.create_website_in_backend()
    github.api.rename_branch.assert_called_once_with(ANY, "testing")
    github.api.create_branch.assert_any_call(settings.GIT_BRANCH_PREVIEW, "testing")
    github.api.create_branch.assert_any_call(settings.GIT_BRANCH_RELEASE, "testing")
    assert new_repo == github.api.get_repo()


def test_create_backend_two_branches_already_exist(settings, github):
    """ Test that the create_backend function only creates branches that don't exist """
    github.api.create_repo.return_value.get_branches.return_value = github.branches[0:2]
    new_repo = github.backend.create_website_in_backend()
    github.repo.rename_branch.assert_not_called()
    with pytest.raises(AssertionError):
        github.api.create_branch.assert_any_call(
            settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_MAIN
        )
    github.api.create_branch.assert_any_call(
        settings.GIT_BRANCH_RELEASE, settings.GIT_BRANCH_MAIN
    )
    assert new_repo == github.api.get_repo()


def test_create_content_in_backend(github):
    """Test that create_content_in_backend calls the appropriate api wrapper function and args"""
    content = github.backend.website.websitecontent_set.all().last()
    content_sync_state = content.content_sync_state
    initial_sha = content_sync_state.current_checksum
    assert initial_sha != content_sync_state.synced_checksum
    github.backend.create_content_in_backend(content.content_sync_state)
    github.api.upsert_content_file.assert_called_once_with(
        content, f"Create {content.content_filepath}"
    )
    updated_sync = ContentSyncState.objects.get(id=content_sync_state.id)
    assert updated_sync.current_checksum == updated_sync.synced_checksum


def test_update_content_in_backend(github):
    """Test that update_content_in_backend calls the appropriate api wrapper function and args"""
    content = github.backend.website.websitecontent_set.all().last()
    github.backend.update_content_in_backend(content.content_sync_state)
    github.api.upsert_content_file.assert_called_once_with(
        content, f"Modify {content.content_filepath}"
    )


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
    """Test that create_backend_release makes the appropriate api merge call"""
    github.backend.create_backend_release()
    github.api.merge_branches.assert_called_once_with(
        settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE
    )


def test_create_content_in_db(mocker, github):
    """Test that create_content_in_db makes the appropriate api call"""
    mock_content_file = mocker.Mock()
    github.backend.create_content_in_db(mock_content_file)
    github.api.format_file_to_content.assert_called_once_with(mock_content_file)


def test_update_content_in_db(mocker, github):
    """Test that update_content_in_db makes the appropriate api call"""
    mock_content_file = mocker.Mock()
    github.backend.update_content_in_db(mock_content_file)
    github.api.format_file_to_content.assert_called_once_with(mock_content_file)


def test_delete_content_in_db(github):
    """Test that delete_content_in_db makes the appropriate api call"""
    sync_state = github.backend.website.websitecontent_set.first().content_sync_state
    github.backend.delete_content_in_db(sync_state)
    assert ContentSyncState.objects.filter(id=sync_state.id).first() is None
    assert WebsiteContent.objects.filter(id=sync_state.content.id).first() is None


def test_sync_all_content_to_db(mocker, github):
    """Test that sync_all_content_to_db iterates over all repo content"""

    def mock_format_file_to_content(content_file):
        """
        Used to replace the mock function of github.api.format_file_to_content
        """
        return convert_data_to_content(
            content_file.path,
            str(b64decode(content_file.content), encoding="utf-8"),
            github.backend.website,
            github.backend.website.uuid,
        )

    existing_content = github.backend.website.websitecontent_set.last()
    repo_content = [
        mocker.Mock(type=ftype, path=path, content=b64encode(content.encode("utf-8")))
        for (ftype, path, content) in [
            ["dir", "src", ""],
            [
                "file",
                "src/__index_test_sync.md",
                "---\nuid: 1\nlayout: course_section\n---\nfile 1 content",
            ],
            [
                "file",
                "src/syllabus_test_sync.md",
                "---\nuid: 2\nlayout: course_section\n---\nfile 2 content",
            ],
            [
                "file",
                "src/readme_test_sync.md",
                "---\nuid: 3\nlayout: course_home\n---\nfile 3 content",
            ],
            [
                "file",
                existing_content.content_filepath,
                "---\nuid: 4\nlayout: course_section\n---\nfile 4 content",
            ],
        ]
    ]
    github.api.get_repo.return_value.get_contents.side_effect = [
        repo_content[0:1],
        repo_content[1:],
    ]

    github.api.format_file_to_content = mock_format_file_to_content

    github.backend.sync_all_content_to_db()
    assert github.backend.website.websitecontent_set.count() == 4

    for content in repo_content:
        if content.type == "file":
            new_content = WebsiteContent.objects.get(
                website=github.backend.website, content_filepath=content.path
            )
            assert new_content.content_sync_state.is_synced
