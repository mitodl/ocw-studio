""" Content sync task tests """
from datetime import timedelta

import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals
from github.GithubException import RateLimitExceededException
from mitol.common.utils import now_in_utc

from content_sync.factories import ContentSyncStateFactory
from content_sync.tasks import (
    create_website_backend,
    sync_all_websites,
    sync_content,
    sync_website_content,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory


pytestmark = pytest.mark.django_db


def test_sync_content(mocker):
    """ Verify the sync_content task calls the corresponding API method """
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    sync_state = ContentSyncStateFactory.create()
    sync_content.delay(sync_state.id)

    log_mock.debug.assert_not_called()
    api_mock.sync_content.assert_called_once_with(sync_state)


def test_sync_content_not_exists(mocker):
    """ Verify the sync_content task does not call the corresponding API method """
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    sync_content.delay(12354)
    log_mock.debug.assert_called_once_with(
        "Attempted to sync ContentSyncState that doesn't exist: id=%s",
        12354,
    )
    api_mock.sync_content.assert_not_called()


def test_create_website_backend(mocker):
    """Verify the create_website_backend task calls the appropriate API and backend methods"""
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    website = WebsiteFactory.create()
    create_website_backend.delay(website.name)

    log_mock.debug.assert_not_called()
    api_mock.get_sync_backend.assert_called_once_with(website)
    api_mock.get_sync_backend.return_value.create_website_in_backend.assert_called_once()


def test_create_website_backend_not_exists(mocker):
    """ Verify the create_website_backend task does not call API and backend methods """
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    create_website_backend.delay("fakesite")

    log_mock.debug.assert_called_once_with(
        "Attempted to create backend for Website that doesn't exist: name=%s",
        "fakesite",
    )
    api_mock.get_sync_backend.assert_not_called()


def test_sync_website_content(mocker):
    """Verify the sync_website_content task calls the appropriate API and backend methods"""
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    website = WebsiteFactory.create()
    sync_website_content.delay(website.name)

    log_mock.debug.assert_not_called()
    api_mock.get_sync_backend.assert_called_once_with(website)
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_called_once()


def test_sync_website_content_not_exists(mocker):
    """Verify the sync_website_content task does not call API and backend methods for nonexistent site"""
    api_mock = mocker.patch("content_sync.tasks.api")
    log_mock = mocker.patch("content_sync.tasks.log")

    sync_website_content.delay("fakesite")

    log_mock.debug.assert_called_once_with(
        "Attempted to update backend for Website that doesn't exist: name=%s",
        "fakesite",
    )
    api_mock.get_sync_backend.assert_not_called()


def test_sync_all_websites(mocker, settings):
    """
    Test that sync_all_content_to_backend is run on all websites needing a sync
    """
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    api_mock = mocker.patch("content_sync.tasks.api")
    website_synced = WebsiteFactory.create()
    websites_unsynced = WebsiteFactory.create_batch(2)
    with mute_signals(post_save):
        ContentSyncStateFactory.create(
            current_checksum="a1",
            synced_checksum="a1",
            content=WebsiteContentFactory.create(website=website_synced),
        )
    ContentSyncStateFactory.create_batch(
        2, content=WebsiteContentFactory.create(website=websites_unsynced[0])
    )
    ContentSyncStateFactory.create_batch(
        2, content=WebsiteContentFactory.create(website=websites_unsynced[1])
    )

    sync_all_websites.delay()
    for website in websites_unsynced:
        api_mock.get_sync_backend.assert_any_call(website)
    with pytest.raises(AssertionError):
        api_mock.get_sync_backend.assert_any_call(website_synced)
    assert (
        api_mock.get_sync_backend.return_value.sync_all_content_to_backend.call_count
        == 2
    )


def test_sync_all_websites_rate_limit_low(mocker, settings):
    """Test that sync_all_websites pauses if the GithubBackend is close to exceeding rate limit"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_git_wrapper = mocker.patch("content_sync.backends.github.GithubApiWrapper")
    sleep_mock = mocker.patch("content_sync.tasks.sleep")
    mock_dt_now = mocker.patch(
        "content_sync.tasks.now_in_utc", now=mocker.Mock(return_value=now_in_utc())
    )
    mock_core = mocker.MagicMock(
        remaining=5, reset=mock_dt_now + timedelta(seconds=1000)
    )
    mock_git_wrapper.return_value.git.get_rate_limit.return_value.core = mock_core
    ContentSyncStateFactory.create_batch(2)
    sync_all_websites.delay()
    assert sleep_mock.call_count == 2


def test_sync_all_websites_rate_limit_exceeded(mocker, settings):
    """Test that sync_all_websites halts if instantiating a GithubBackend exceeds the rate limit"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    api_mock = mocker.patch("content_sync.tasks.api")
    api_mock.get_sync_backend.side_effect = RateLimitExceededException(
        status=403, data={}
    )
    ContentSyncStateFactory.create_batch(2)
    with pytest.raises(RateLimitExceededException):
        sync_all_websites.delay()
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_not_called()
