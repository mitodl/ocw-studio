""" Content sync api tests """
import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals

from content_sync import api
from websites.factories import WebsiteContentFactory, WebsiteFactory


pytestmark = pytest.mark.django_db


def test_upsert_content_sync_state_create():
    """ Verify that upsert_content_sync_state creates a ContentSyncState record for the content """
    with mute_signals(post_save):
        content = WebsiteContentFactory.create(markdown="abc")

    assert getattr(content, "content_sync_state", None) is None

    api.upsert_content_sync_state(content)

    content.refresh_from_db()

    abc_checksum = content.calculate_checksum()

    assert content.content_sync_state is not None
    assert content.content_sync_state.synced_checksum is None
    assert content.content_sync_state.current_checksum == abc_checksum


def test_upsert_content_sync_state_update(settings):
    """ Verify that upsert_content_sync_state updates a ContentSyncState record for the content """
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    content = WebsiteContentFactory.create(markdown="abc")
    abc_checksum = content.calculate_checksum()

    sync_state = content.content_sync_state
    sync_state.current_checksum = abc_checksum
    sync_state.synced_checksum = abc_checksum
    sync_state.save()

    content.markdown = "def"

    def_checksum = content.calculate_checksum()

    with mute_signals(post_save):
        content.save()

    api.upsert_content_sync_state(content)

    content.content_sync_state.refresh_from_db()
    assert content.content_sync_state.synced_checksum == abc_checksum
    assert content.content_sync_state.current_checksum == def_checksum


def test_get_sync_backend(settings, mocker):
    """ Verify that get_sync_backend() imports the backend based on settings.py """
    settings.CONTENT_SYNC_BACKEND = "custom.backend.Backend"
    import_string_mock = mocker.patch("content_sync.api.import_string")
    website = WebsiteFactory.create()
    api.get_sync_backend(website)
    import_string_mock.assert_any_call("custom.backend.Backend")
    import_string_mock.return_value.assert_any_call(website)


def test_sync_content_enabled(settings, mocker):
    """ Verify sync_content doesn't run anything is sync is disabled """
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mocker.patch("content_sync.api.is_sync_enabled", return_value=True)
    log_mock = mocker.patch("content_sync.api.log")
    get_sync_backend_mock = mocker.patch("content_sync.api.get_sync_backend")
    sync_state = mocker.Mock()

    api.sync_content(sync_state)

    log_mock.debug.assert_not_called()
    get_sync_backend_mock.assert_called_once_with(sync_state.content.website)
    get_sync_backend_mock.return_value.sync_content_to_backend.assert_called_once_with(
        sync_state
    )


def test_sync_content_disabled(settings, mocker):
    """ Verify sync_content doesn't run anything is sync is disabled """
    settings.CONTENT_SYNC_BACKEND = None
    mocker.patch("content_sync.api.is_sync_enabled", return_value=False)
    get_sync_backend_mock = mocker.patch("content_sync.api.get_sync_backend")
    api.sync_content(None)
    get_sync_backend_mock.assert_not_called()


def test_create_website_backend(settings, mocker):
    """Verify create_website_backend calls the appropriate task"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mocker.patch("content_sync.api.is_sync_enabled", return_value=True)
    mock_task = mocker.patch("content_sync.tasks.create_website_backend")
    with mute_signals(post_save):
        website = WebsiteFactory.create()
    api.create_website_backend(website)
    mock_task.delay.assert_called_once_with(website.name)


def test_create_website_backend_disabled(settings, mocker):
    """Verify create_website_backend doesn't do anything if syncing is disabled"""
    settings.CONTENT_SYNC_BACKEND = ""
    mocker.patch("content_sync.api.is_sync_enabled", return_value=False)
    mock_task = mocker.patch("content_sync.tasks.create_website_backend")
    with mute_signals(post_save):
        website = WebsiteFactory.create()
    api.create_website_backend(website)
    mock_task.delay.assert_not_called()


def test_update_website_backend(settings, mocker):
    """Verify update_website_backend calls the appropriate task"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mocker.patch("content_sync.api.is_sync_enabled", return_value=True)
    mock_task = mocker.patch("content_sync.tasks.sync_website_content")
    website = WebsiteFactory.create()
    api.update_website_backend(website)
    mock_task.delay.assert_called_once_with(website.name)


def test_update_website_backend_disabled(settings, mocker):
    """Verify update_website_backend doesn't do anything if syncing is disabled"""
    settings.CONTENT_SYNC_BACKEND = None
    mocker.patch("content_sync.api.is_sync_enabled", return_value=False)
    mock_task = mocker.patch("content_sync.tasks.sync_website_content")
    website = WebsiteFactory.create()
    api.update_website_backend(website)
    mock_task.delay.assert_not_called()


def test_preview_website(settings, mocker):
    """Verify preview_website calls the appropriate task"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mock_task = mocker.patch("content_sync.tasks.preview_website_backend")
    website = WebsiteFactory.create()
    api.preview_website(website)
    mock_task.delay.assert_called_once_with(website.name)


def test_publish_website(settings, mocker):
    """Verify publish_website calls the appropriate task"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mock_task = mocker.patch("content_sync.tasks.publish_website_backend")
    website = WebsiteFactory.create()
    api.publish_website(website)
    mock_task.delay.assert_called_once_with(website.name)
