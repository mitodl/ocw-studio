""" Content sync task tests """
import datetime
from datetime import timedelta

import pytest
import pytz
from django.db.models.signals import post_save
from factory.django import mute_signals
from github.GithubException import RateLimitExceededException
from mitol.common.utils import now_in_utc
from pytest import fixture

from content_sync import tasks
from content_sync.factories import ContentSyncStateFactory
from content_sync.pipelines.base import BaseSyncPipeline
from websites.constants import (
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_PENDING,
    PUBLISH_STATUS_SUCCEEDED,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory


pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@fixture
def api_mock(mocker, settings):
    """Return a mocked content_sync.tasks.api, and set the backend"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE = "content_sync.pipelines.TestPipeline"
    return mocker.patch("content_sync.tasks.api")


@fixture
def log_mock(mocker):
    """ Return a mocked log object"""
    return mocker.patch("content_sync.tasks.log")


def test_sync_content(api_mock, log_mock):
    """ Verify the sync_content task calls the corresponding API method """
    sync_state = ContentSyncStateFactory.create()
    tasks.sync_content.delay(sync_state.id)

    log_mock.debug.assert_not_called()
    api_mock.sync_content.assert_called_once_with(sync_state)


def test_sync_content_not_exists(api_mock, log_mock):
    """ Verify the sync_content task does not call the corresponding API method """
    tasks.sync_content.delay(12354)
    log_mock.debug.assert_called_once_with(
        "Attempted to sync ContentSyncState that doesn't exist: id=%s",
        12354,
    )
    api_mock.sync_content.assert_not_called()


def test_create_website_backend(api_mock, log_mock):
    """Verify the create_website_backend task calls the appropriate API and backend methods"""
    website = WebsiteFactory.create()
    tasks.create_website_backend.delay(website.name)

    log_mock.debug.assert_not_called()
    api_mock.get_sync_backend.assert_called_once_with(website)
    api_mock.get_sync_backend.return_value.create_website_in_backend.assert_called_once()


def test_create_website_backend_not_exists(api_mock, log_mock):
    """ Verify the create_website_backend task does not call API and backend methods """
    tasks.create_website_backend.delay("fakesite")

    log_mock.debug.assert_called_once_with(
        "Attempted to create backend for Website that doesn't exist: name=%s",
        "fakesite",
    )
    api_mock.get_sync_backend.assert_not_called()


def test_sync_website_content(api_mock, log_mock):
    """Verify the sync_website_content task calls the appropriate API and backend methods"""
    website = WebsiteFactory.create()
    tasks.sync_website_content.delay(website.name)

    log_mock.debug.assert_not_called()
    api_mock.get_sync_backend.assert_called_once_with(website)
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_called_once()


def test_sync_website_content_not_exists(api_mock, log_mock):
    """Verify the sync_website_content task does not call API and backend methods for nonexistent site"""
    tasks.sync_website_content.delay("fakesite")

    log_mock.debug.assert_called_once_with(
        "Attempted to update backend for Website that doesn't exist: name=%s",
        "fakesite",
    )
    api_mock.get_sync_backend.assert_not_called()


@pytest.mark.parametrize("backend_exists", [True, False])
@pytest.mark.parametrize("create_backend", [True, False])
def test_sync_all_websites(api_mock, backend_exists, create_backend):
    """
    Test that sync_all_content_to_backend is run on all websites needing a sync
    """
    api_mock.get_sync_backend.return_value.backend_exists.return_value = backend_exists
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

    tasks.sync_all_websites.delay(create_backends=create_backend)
    for website in websites_unsynced:
        api_mock.get_sync_backend.assert_any_call(website)
    with pytest.raises(AssertionError):
        api_mock.get_sync_backend.assert_any_call(website_synced)
    assert (
        api_mock.get_sync_backend.return_value.sync_all_content_to_backend.call_count
        == (2 if (create_backend or backend_exists) else 0)
    )


@pytest.mark.parametrize("check_limit", [True, False])
def test_sync_all_websites_rate_limit_low(mocker, settings, check_limit):
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
    tasks.sync_all_websites.delay(check_limit=check_limit)
    assert sleep_mock.call_count == (2 if check_limit else 0)


def test_sync_all_websites_rate_limit_exceeded(api_mock):
    """Test that sync_all_websites halts if instantiating a GithubBackend exceeds the rate limit"""
    api_mock.get_sync_backend.side_effect = RateLimitExceededException(
        status=403, data={}, headers={}
    )
    ContentSyncStateFactory.create_batch(2)
    with pytest.raises(RateLimitExceededException):
        tasks.sync_all_websites.delay()
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_not_called()


@pytest.mark.parametrize("prepublish_actions", [[], ["some.Action"]])
@pytest.mark.parametrize("has_date", [True, False])
def test_preview_website_backend(
    api_mock, mocker, settings, prepublish_actions, has_date
):
    """Verify that the appropriate backend calls are made by the preview_website_backend task """
    settings.PREPUBLISH_ACTIONS = prepublish_actions
    import_string_mock = mocker.patch("content_sync.tasks.import_string")

    website = WebsiteFactory.create()
    if not has_date:
        website.draft_publish_date = None
        website.save()
    tasks.preview_website_backend(website.name, website.draft_publish_date)
    api_mock.get_sync_backend.assert_called_once_with(website)
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_called_once()
    api_mock.get_sync_backend.return_value.create_backend_preview.assert_called_once()
    if has_date:
        api_mock.unpause_publishing_pipeline.assert_not_called()
    else:
        api_mock.unpause_publishing_pipeline.called_once_with(
            website, BaseSyncPipeline.VERSION_DRAFT
        )

    if len(prepublish_actions) > 0:
        import_string_mock.assert_any_call("some.Action")
        import_string_mock.return_value.assert_any_call(website)


@pytest.mark.parametrize("prepublish_actions", [[], ["some.Action"]])
@pytest.mark.parametrize("has_date", [True, False])
def test_publish_website_backend(
    api_mock, mocker, settings, prepublish_actions, has_date
):
    """Verify that the appropriate backend calls are made by the publish_website_backend task"""
    settings.PREPUBLISH_ACTIONS = prepublish_actions
    import_string_mock = mocker.patch("content_sync.tasks.import_string")

    website = WebsiteFactory.create()
    if not has_date:
        website.publish_date = None
        website.save()
    tasks.publish_website_backend(website.name, website.publish_date)
    api_mock.get_sync_backend.assert_called_once_with(website)
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_called_once()
    api_mock.get_sync_backend.return_value.create_backend_release.assert_called_once()
    if has_date:
        api_mock.unpause_publishing_pipeline.assert_not_called()
    else:
        api_mock.unpause_publishing_pipeline.called_once_with(
            website, BaseSyncPipeline.VERSION_LIVE
        )

    if len(prepublish_actions) > 0:
        import_string_mock.assert_any_call("some.Action")
        import_string_mock.return_value.assert_any_call(website)


@pytest.mark.parametrize(
    "func, version",
    [
        ["preview_website_backend", "draft"],
        ["publish_website_backend", "live"],
    ],
)
def test_preview_publish_backend_error(api_mock, mocker, settings, func, version):
    """Verify that the appropriate error handling occurs if preview/publish_website_backend throws an exception"""
    settings.PREPUBLISH_ACTIONS = [["some.Action"]]
    mocker.patch("content_sync.tasks.import_string", side_effect=Exception("error"))
    mock_email_admins = mocker.patch(
        "content_sync.tasks.mail_website_admins_on_publish"
    )
    website = WebsiteFactory.create()
    method_call = getattr(tasks, func)
    method_call(website.name, website.draft_publish_date)
    api_mock.get_sync_backend.assert_not_called()
    mock_email_admins.assert_called_once_with(website, version, False)


def test_sync_github_site_configs(mocker):
    """ sync_github_site_configs should call apis.github.sync_starter_configs with same args, kwargs"""
    mock_git = mocker.patch("content_sync.tasks.github")
    args = "https://github.com/testorg/testconfigs", ["site1/studio.yaml"]
    kwargs = {"commit": "abc123"}
    tasks.sync_github_site_configs.delay(*args, **kwargs)
    mock_git.sync_starter_configs.assert_called_once_with(*args, **kwargs)


def test_upsert_web_publishing_pipeline(api_mock):
    """ upsert_web_publishing_pipeline should call api.get_sync_pipeline"""
    website = WebsiteFactory.create()
    tasks.upsert_website_publishing_pipeline.delay(website.name)
    api_mock.get_sync_pipeline.assert_called_once_with(website)


def test_upsert_web_publishing_pipeline_missing(api_mock, log_mock):
    """ upsert_web_publishing_pipeline should log a debug message if the website doesn't exist"""
    tasks.upsert_website_publishing_pipeline.delay("fake")
    log_mock.debug.assert_called_once_with(
        "Attempted to create pipeline for Website that doesn't exist: name=%s",
        "fake",
    )
    api_mock.get_sync_pipeline.assert_not_called()


@pytest.mark.parametrize(
    "final_status",
    [
        PUBLISH_STATUS_SUCCEEDED,
        PUBLISH_STATUS_ERRORED,
        PUBLISH_STATUS_ABORTED,
    ],
)
@pytest.mark.parametrize("version", ["draft", "live"])
def test_poll_build_status_until_complete(mocker, api_mock, final_status, version):
    """poll_build_status_until_complete should repeatedly poll until a finished state is reached"""
    website = WebsiteFactory.create(
        has_unpublished_live=False, has_unpublished_draft=False
    )
    now_dates = [
        datetime.datetime(2020, 1, 1, tzinfo=pytz.utc),
        datetime.datetime(2020, 2, 1, tzinfo=pytz.utc),
        datetime.datetime(2020, 3, 1, tzinfo=pytz.utc),
    ]
    mocker.patch("content_sync.tasks.now_in_utc", side_effect=now_dates)
    latest_status_mock = api_mock.get_sync_pipeline.return_value.get_latest_build_status
    latest_status_mock.side_effect = [
        PUBLISH_STATUS_NOT_STARTED,
        PUBLISH_STATUS_PENDING,
        final_status,
    ]
    final_now_date = now_dates[2]
    tasks.poll_build_status_until_complete.delay(
        website.name, version, final_now_date.isoformat()
    )
    website.refresh_from_db()
    if version == "draft":
        assert website.draft_publish_status == final_status
        assert website.draft_publish_status_updated_on == final_now_date
        assert website.draft_publish_date == final_now_date
        assert website.has_unpublished_draft == (
            final_status != PUBLISH_STATUS_SUCCEEDED
        )
    else:
        assert website.live_publish_status == final_status
        assert website.live_publish_status_updated_on == final_now_date
        assert website.publish_date == final_now_date
        assert website.has_unpublished_live == (
            final_status != PUBLISH_STATUS_SUCCEEDED
        )

    assert latest_status_mock.call_count == 3
    latest_status_mock.assert_any_call(version)
    api_mock.get_sync_pipeline.assert_any_call(website)
    assert api_mock.get_sync_pipeline.call_count == len(now_dates)
