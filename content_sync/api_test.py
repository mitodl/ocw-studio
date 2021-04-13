""" Content sync api tests """
import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals

from content_sync.api import (
    get_sync_backend,
    is_sync_enabled,
    sync_content,
    upsert_content_sync_state,
)
from websites.factories import WebsiteContentFactory


pytestmark = pytest.mark.django_db


def test_upsert_content_sync_state_create(mocker):
    """ Verify that upsert_content_sync_state creates a ContentSyncState record for the content """
    with mute_signals(post_save):
        content = WebsiteContentFactory.create(markdown="abc")

    sync_content_task_mock = mocker.patch("content_sync.api.tasks").sync_content
    mocker.patch(
        "content_sync.api.transaction.on_commit",
        side_effect=lambda callback: callback(),
    )

    assert getattr(content, "content_sync_state", None) is None

    upsert_content_sync_state(content)

    content.refresh_from_db()

    abc_checksum = content.calculate_checksum()

    assert content.content_sync_state is not None
    assert content.content_sync_state.synced_checksum is None
    assert content.content_sync_state.current_checksum == abc_checksum

    sync_content_task_mock.delay.assert_called_once_with(content.content_sync_state.id)


def test_upsert_content_sync_state_update(mocker):
    """ Verify that upsert_content_sync_state updates a ContentSyncState record for the content """
    content = WebsiteContentFactory.create(markdown="abc")

    sync_content_task_mock = mocker.patch("content_sync.api.tasks").sync_content
    mocker.patch(
        "content_sync.api.transaction.on_commit",
        side_effect=lambda callback: callback(),
    )

    abc_checksum = content.calculate_checksum()

    content.content_sync_state.mark_synced()
    content.markdown = "def"

    def_checksum = content.calculate_checksum()

    with mute_signals(post_save):
        content.save()

    upsert_content_sync_state(content)

    content.content_sync_state.refresh_from_db()
    assert content.content_sync_state.synced_checksum == abc_checksum
    assert content.content_sync_state.current_checksum == def_checksum

    sync_content_task_mock.delay.assert_called_once_with(content.content_sync_state.id)


def test_is_sync_enabled(settings):
    """ Verify that is_sync_enabled returns true if the value is set """
    settings.CONTENT_SYNC_BACKEND = "abc"
    assert is_sync_enabled() is True
    settings.CONTENT_SYNC_BACKEND = None
    assert is_sync_enabled() is False
    del settings.CONTENT_SYNC_BACKEND
    assert is_sync_enabled() is False


def test_get_sync_backend(settings, mocker):
    """ Verify that get_sync_backend() imports the backend based on settings.py """
    settings.CONTENT_SYNC_BACKEND = "custom.backend.Backend"
    import_string_mock = mocker.patch("content_sync.api.import_string")

    assert get_sync_backend() == import_string_mock.return_value

    import_string_mock.assert_called_once_with("custom.backend.Backend")


def test_sync_content_enabled(mocker):
    """ Verify sync_content doesn't run anything is sync is disabled """
    mocker.patch("content_sync.api.is_sync_enabled", return_value=True)
    log_mock = mocker.patch("content_sync.api.log")
    get_sync_backend_mock = mocker.patch("content_sync.api.get_sync_backend")
    sync_state = mocker.Mock()

    sync_content(sync_state)

    log_mock.debug.assert_not_called()
    get_sync_backend_mock.assert_called_once_with()
    get_sync_backend_mock.return_value.sync_content_to_backend(sync_state)


def test_sync_content_disabled(mocker):
    """ Verify sync_content doesn't run anything is sync is disabled """
    mocker.patch("content_sync.api.is_sync_enabled", return_value=False)
    log_mock = mocker.patch("content_sync.api.log")
    get_sync_backend_mock = mocker.patch("content_sync.api.get_sync_backend")

    sync_content(None)

    log_mock.debug.assert_called_once_with("Syncing is disabled")
    get_sync_backend_mock.assert_not_called()
