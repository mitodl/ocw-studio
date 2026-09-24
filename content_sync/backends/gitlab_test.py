"""GitLab backend tests"""

from base64 import b64encode
from types import SimpleNamespace

import pytest

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.backends.gitlab import GitlabBackend
from content_sync.models import ContentSyncState
from content_sync.utils import get_destination_filepath
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig

pytestmark = pytest.mark.django_db


@pytest.fixture
def gitlab(settings, mocker):
    """Create a GitLab backend for a website."""
    settings.GIT_TOKEN = "faketoken"  # noqa: S105
    settings.GIT_API_URL = "https://gitlab.example.com"
    settings.GIT_ORGANIZATION = "fake_group"
    mock_gitlab_api = mocker.patch("content_sync.backends.gitlab.GitlabApiWrapper")

    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(5, website=website)
    backend = GitlabBackend(website)
    backend.api = mock_gitlab_api
    return SimpleNamespace(
        backend=backend,
        api=mock_gitlab_api,
    )


@pytest.fixture
def gitlab_content_file(mocker):
    """Fixture that returns a mocked GitLab file object and decoded content."""
    content_str = "my file content"
    file_path = "/path/to/file.md"
    return SimpleNamespace(
        obj=mocker.Mock(
            content=b64encode(content_str.encode("utf-8")), file_path=file_path
        ),
        file_path=file_path,
        content_str=content_str,
    )


@pytest.fixture
def patched_file_deserialize(mocker):
    """Patch function that deserializes file contents to website content."""
    return mocker.patch(
        "content_sync.backends.gitlab.deserialize_file_to_website_content"
    )


@pytest.mark.parametrize("exists", [True, False])
def test_backend_exists(gitlab, exists):
    """backend_exists should return the expected boolean value."""
    gitlab.api.repo_exists.return_value = exists
    assert gitlab.backend.backend_exists() is exists


def test_create_website_in_backend(gitlab):
    """create_website_in_backend should call API create_repo."""
    gitlab.backend.create_website_in_backend()
    gitlab.api.create_repo.assert_called_once()


def test_create_content_in_backend(gitlab):
    """create_content_in_backend should call API upsert_content_file."""
    content = gitlab.backend.website.websitecontent_set.all().last()
    content_sync_state = content.content_sync_state
    gitlab.backend.create_content_in_backend(content_sync_state)
    gitlab.api.upsert_content_file.assert_called_once_with(content)


def test_update_content_in_backend(gitlab):
    """update_content_in_backend should call API upsert_content_file."""
    content = gitlab.backend.website.websitecontent_set.all().last()
    gitlab.backend.update_content_in_backend(content.content_sync_state)
    gitlab.api.upsert_content_file.assert_called_once_with(content)


def test_delete_content_in_backend(gitlab):
    """delete_content_in_backend should call API delete_content_file."""
    content = gitlab.backend.website.websitecontent_set.all().last()
    content_sync_state = content.content_sync_state
    gitlab.backend.delete_content_in_backend(content_sync_state)
    gitlab.api.delete_content_file.assert_called_once_with(content)
    assert ContentSyncState.objects.filter(id=content_sync_state.id).first() is None
    assert WebsiteContent.objects.filter(id=content.id).first() is None


def test_sync_all_content_to_backend(gitlab):
    """sync_all_content_to_backend should call API upsert_content_files."""
    gitlab.backend.sync_all_content_to_backend()
    gitlab.api.upsert_content_files.assert_called_once()


def test_create_backend_draft(settings, gitlab):
    """merge_backend_draft should sync content and merge main->preview."""
    gitlab.backend.merge_backend_draft()
    gitlab.api.upsert_content_files.assert_called_once()
    gitlab.api.merge_branches.assert_called_once_with(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
    )


def test_create_backend_live(settings, gitlab):
    """merge_backend_live should merge main->preview and main->release."""
    gitlab.backend.merge_backend_live()
    gitlab.api.merge_branches.assert_any_call(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_PREVIEW
    )
    gitlab.api.merge_branches.assert_any_call(
        settings.GIT_BRANCH_MAIN, settings.GIT_BRANCH_RELEASE
    )


def test_create_content_in_db(gitlab, gitlab_content_file, patched_file_deserialize):
    """create_content_in_db should deserialize GitLab file content."""
    gitlab.backend.create_content_in_db(gitlab_content_file.obj)
    patched_file_deserialize.assert_called_once_with(
        site_config=gitlab.backend.site_config,
        website=gitlab.backend.website,
        filepath=gitlab_content_file.file_path,
        file_contents=gitlab_content_file.content_str,
    )


def test_update_content_in_db(gitlab, gitlab_content_file, patched_file_deserialize):
    """update_content_in_db should deserialize GitLab file content."""
    gitlab.backend.update_content_in_db(gitlab_content_file.obj)
    patched_file_deserialize.assert_called_once_with(
        site_config=gitlab.backend.site_config,
        website=gitlab.backend.website,
        filepath=gitlab_content_file.file_path,
        file_contents=gitlab_content_file.content_str,
    )


def test_delete_content_in_db(gitlab):
    """delete_content_in_db should remove WebsiteContent and ContentSyncState."""
    sync_state = gitlab.backend.website.websitecontent_set.first().content_sync_state
    gitlab.backend.delete_content_in_db(sync_state)
    assert ContentSyncState.objects.filter(id=sync_state.id).first() is None
    assert WebsiteContent.objects.filter(id=sync_state.content.id).first() is None


def test_delete_orphaned_content_in_backend(gitlab):
    """delete_orphaned_content_in_backend should call batch_delete_files correctly."""
    prior_path = "content/old/pages/1.md"
    content = gitlab.backend.website.websitecontent_set.all()
    ContentSyncState.objects.filter(content=content[2]).update(
        data={GIT_DATA_FILEPATH: prior_path}
    )
    paths_to_delete = ["content/nomatch/1.md", "content/nomatch/2.md"]
    gitlab.api.site_config = SiteConfig(gitlab.backend.website.starter.config)
    gitlab.api.get_all_file_paths.return_value = iter(
        [
            get_destination_filepath(content[0], gitlab.backend.api.site_config),
            get_destination_filepath(content[1], gitlab.backend.api.site_config),
            prior_path,
            *paths_to_delete,
        ]
    )
    gitlab.backend.delete_orphaned_content_in_backend()
    gitlab.api.get_all_file_paths.assert_called_once_with("")
    gitlab.api.batch_delete_files.assert_called_once_with([*paths_to_delete])
