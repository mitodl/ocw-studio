""" Content sync task tests """
import pytest

from content_sync.factories import ContentSyncStateFactory
from content_sync.tasks import sync_content


@pytest.mark.django_db
def test_sync_content(mocker):
    """ Verify the sync_content tasks calls the corresponding API method """
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    sync_state = ContentSyncStateFactory.create()
    sync_content.delay(sync_state.id)

    log_mock.debug.assert_not_called()
    api_mock.sync_content.assert_called_once_with(sync_state)


@pytest.mark.django_db
def test_sync_content_not_exists(mocker):
    """ Verify the sync_content tasks calls the corresponding API method """
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    sync_content.delay(12354)
    log_mock.debug.assert_called_once_with(
        "Attempted to sync ContentSyncState that doesn't exist: id=%s",
        12354,
    )
    api_mock.sync_content.assert_not_called()
