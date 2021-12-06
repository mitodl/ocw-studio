""" Content sync task tests """
from datetime import timedelta

import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals
from github.GithubException import RateLimitExceededException
from mitol.common.utils import now_in_utc
from pytest import fixture
from requests import HTTPError

from content_sync import tasks
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.factories import ContentSyncStateFactory
from websites.constants import (
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_STARTED,
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
def test_sync_unsynced_websites(api_mock, backend_exists, create_backend):
    """
    Test that sync_all_content_to_backend is run on all websites needing a sync
    """
    api_mock.get_sync_backend.return_value.backend_exists.return_value = backend_exists
    website_synced = WebsiteFactory.create(
        has_unpublished_live=False,
        has_unpublished_draft=False,
        live_publish_status=PUBLISH_STATUS_SUCCEEDED,
        draft_publish_status=PUBLISH_STATUS_SUCCEEDED,
        latest_build_id_live=1,
        latest_build_id_draft=2,
    )
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

    tasks.sync_unsynced_websites.delay(create_backends=create_backend)
    for website in websites_unsynced:
        api_mock.get_sync_backend.assert_any_call(website)
        website.refresh_from_db()
        assert website.has_unpublished_live is True
        assert website.has_unpublished_draft is True
        assert website.live_publish_status is None
        assert website.draft_publish_status is None
        assert website.latest_build_id_live is None
        assert website.latest_build_id_draft is None
    with pytest.raises(AssertionError):
        api_mock.get_sync_backend.assert_any_call(website_synced)
    assert (
        api_mock.get_sync_backend.return_value.sync_all_content_to_backend.call_count
        == (2 if (create_backend or backend_exists) else 0)
    )


@pytest.mark.parametrize("check_limit", [True, False])
def test_sync_all_websites_rate_limit_low(mocker, settings, check_limit):
    """Test that sync_unsynced_websites pauses if the GithubBackend is close to exceeding rate limit"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_git_wrapper = mocker.patch("content_sync.backends.github.GithubApiWrapper")
    sleep_mock = mocker.patch("content_sync.tasks.sleep")
    mock_dt_now = mocker.patch(
        "content_sync.tasks.now_in_utc", return_value=now_in_utc()
    )
    mock_core = mocker.MagicMock(
        remaining=5, reset=mock_dt_now + timedelta(seconds=1000)
    )
    mock_git_wrapper.return_value.git.get_rate_limit.return_value.core = mock_core
    ContentSyncStateFactory.create_batch(2)
    tasks.sync_unsynced_websites.delay(check_limit=check_limit)
    assert sleep_mock.call_count == (2 if check_limit else 0)


def test_sync_all_websites_rate_limit_exceeded(api_mock):
    """Test that sync_unsynced_websites halts if instantiating a GithubBackend exceeds the rate limit"""
    api_mock.get_sync_backend.side_effect = RateLimitExceededException(
        status=403, data={}, headers={}
    )
    ContentSyncStateFactory.create_batch(2)
    with pytest.raises(RateLimitExceededException):
        tasks.sync_unsynced_websites.delay()
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_not_called()


def test_publish_website_backend_draft(api_mock):
    """Verify that the appropriate backend calls are made by the publish_website_backend_draft task """
    website = WebsiteFactory.create()
    tasks.publish_website_backend_draft(website.name)
    api_mock.publish_website.assert_called_once_with(website.name, VERSION_DRAFT)


def test_publish_website_backend_draft_error(mocker, api_mock):
    """Verify that the expected logging statement and return value are made if an error occurs"""
    api_mock.publish_website.side_effect = Exception()
    mock_log = mocker.patch("content_sync.tasks.log.exception")
    website = WebsiteFactory.create()
    result = tasks.publish_website_backend_draft(website.name)
    mock_log.assert_called_once_with("Error publishing draft site %s", website.name)
    assert result == website.name


def test_publish_website_backend_live(api_mock):
    """Verify that the appropriate backend calls are made by the publish_website_backend_live task"""
    website = WebsiteFactory.create()
    tasks.publish_website_backend_live(website.name)
    api_mock.publish_website.assert_called_once_with(website.name, VERSION_LIVE)


def test_publish_website_backend_live_error(mocker, api_mock):
    """Verify that the expected logging statement and return value are made if an error occurs"""
    api_mock.publish_website.side_effect = Exception()
    mock_log = mocker.patch("content_sync.tasks.log.exception")
    website = WebsiteFactory.create()
    result = tasks.publish_website_backend_live(website.name)
    mock_log.assert_called_once_with("Error publishing live site %s", website.name)
    assert result == website.name


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


@pytest.mark.parametrize("create_backend", [True, False])
@pytest.mark.parametrize("unpause", [True, False])
@pytest.mark.parametrize("chunk_size, chunks", [[3, 1], [2, 2]])
def test_upsert_pipelines(  # pylint:disable=too-many-arguments, unused-argument
    mocker, mocked_celery, create_backend, unpause, chunk_size, chunks
):
    """upsert_pipelines calls upsert_pipeline_batch with correct arguments"""
    websites = WebsiteFactory.create_batch(3)
    website_names = sorted([website.name for website in websites])
    mock_batch = mocker.patch("content_sync.tasks.upsert_website_pipeline_batch.s")
    with pytest.raises(TabError):
        tasks.upsert_pipelines.delay(
            website_names,
            create_backend=create_backend,
            unpause=unpause,
            chunk_size=chunk_size,
        )
    mock_batch.assert_any_call(
        website_names[0:chunk_size], create_backend=create_backend, unpause=unpause
    )
    if chunks > 1:
        mock_batch.assert_any_call(
            website_names[chunk_size:], create_backend=create_backend, unpause=unpause
        )


@pytest.mark.parametrize("create_backend", [True, False])
@pytest.mark.parametrize("unpause", [True, False])
def test_upsert_website_pipeline_batch(mocker, create_backend, unpause):
    """upsert_website_pipeline_batch should make the expected function calls"""
    mock_get_backend = mocker.patch("content_sync.tasks.api.get_sync_backend")
    mock_get_pipeline = mocker.patch("content_sync.tasks.api.get_sync_pipeline")
    websites = WebsiteFactory.create_batch(2)
    website_names = sorted([website.name for website in websites])
    tasks.upsert_website_pipeline_batch(
        website_names, create_backend=create_backend, unpause=unpause
    )
    mock_get_pipeline.assert_any_call(websites[0], api=None)
    mock_get_pipeline.assert_any_call(websites[1], api=mocker.ANY)
    if create_backend:
        for website in websites:
            mock_get_backend.assert_any_call(website)
        mock_backend = mock_get_backend.return_value
        assert mock_backend.create_website_in_backend.call_count == 2
        assert mock_backend.sync_all_content_to_backend.call_count == 2
    else:
        mock_get_backend.assert_not_called()
    mock_pipeline = mock_get_pipeline.return_value
    assert mock_pipeline.upsert_website_pipeline.call_count == 2
    if unpause:
        mock_pipeline.unpause_pipeline.assert_any_call(VERSION_DRAFT)
        mock_pipeline.unpause_pipeline.assert_any_call(VERSION_LIVE)
    else:
        mock_pipeline.unpause_pipeline.assert_not_called()


@pytest.mark.parametrize("prepublish", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize("chunk_size, chunks", [[3, 1], [2, 2]])
def test_publish_websites(  # pylint:disable=unused-argument,too-many-arguments
    mocker, mocked_celery, api_mock, version, chunk_size, chunks, prepublish
):
    """publish_websites calls upsert_pipeline_batch with correct arguments"""
    websites = WebsiteFactory.create_batch(3)
    website_names = sorted([website.name for website in websites])
    mock_batch = mocker.patch("content_sync.tasks.publish_website_batch.s")
    with pytest.raises(TabError):
        tasks.publish_websites.delay(
            website_names, version, chunk_size=chunk_size, prepublish=prepublish
        )
    mock_batch.assert_any_call(
        website_names[0:chunk_size], version, prepublish=prepublish
    )
    if chunks > 1:
        mock_batch.assert_any_call(
            website_names[chunk_size:], version, prepublish=prepublish
        )


@pytest.mark.parametrize("prepublish", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_publish_website_batch(mocker, version, prepublish):
    """publish_website_batch should make the expected function calls"""
    mock_import_string = mocker.patch("content_sync.tasks.import_string")
    mock_publish_website = mocker.patch("content_sync.api.publish_website")
    website_names = sorted([website.name for website in WebsiteFactory.create_batch(3)])
    tasks.publish_website_batch(website_names, version, prepublish=prepublish)
    for name in website_names:
        mock_publish_website.assert_any_call(
            name,
            version,
            pipeline_api=mock_import_string.return_value.get_api.return_value,
            prepublish=prepublish,
        )


@pytest.mark.parametrize(
    "old_status, new_status, should_check, should_update",
    [
        [PUBLISH_STATUS_SUCCEEDED, None, False, False],
        [PUBLISH_STATUS_NOT_STARTED, PUBLISH_STATUS_STARTED, True, True],
        [PUBLISH_STATUS_NOT_STARTED, PUBLISH_STATUS_NOT_STARTED, True, False],
    ],
)
@pytest.mark.parametrize(
    "pipeline", [None, "content_sync.pipelines.concourse.ConcourseGithubPipeline"]
)
def test_check_incomplete_publish_build_statuses(
    settings,
    mocker,
    api_mock,
    old_status,
    new_status,
    should_check,
    should_update,
    pipeline,
):  # pylint:disable=too-many-arguments
    """check_incomplete_publish_build_statuses should update statuses of pipeline builds"""
    settings.CONTENT_SYNC_PIPELINE = pipeline
    mock_update_status = mocker.patch("content_sync.tasks.update_website_status")
    now = now_in_utc()
    draft_site_in_query = WebsiteFactory.create(
        draft_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        draft_publish_status=old_status,
        latest_build_id_draft=1,
    )
    draft_site_to_exclude = WebsiteFactory.create(
        draft_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME - 5),
        draft_publish_status=old_status,
        latest_build_id_draft=2,
    )
    live_site_in_query = WebsiteFactory.create(
        live_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        live_publish_status=old_status,
        latest_build_id_live=3,
    )
    live_site_excluded = WebsiteFactory.create(
        live_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME - 5),
        live_publish_status=old_status,
        latest_build_id_live=4,
    )
    api_mock.get_sync_pipeline.return_value.get_build_status.return_value = new_status
    tasks.check_incomplete_publish_build_statuses.delay()
    for website, version in [
        (draft_site_in_query, VERSION_DRAFT),
        (live_site_in_query, VERSION_LIVE),
    ]:
        if should_check and pipeline is not None:
            api_mock.get_sync_pipeline.assert_any_call(website)
            api_mock.get_sync_pipeline.return_value.get_build_status.assert_any_call(
                getattr(website, f"latest_build_id_{version}")
            )
            if should_update:
                mock_update_status.assert_any_call(
                    website, version, new_status, mocker.ANY
                )
        else:
            with pytest.raises(AssertionError):
                api_mock.get_sync_pipeline.assert_any_call(website)
            with pytest.raises(AssertionError):
                mock_update_status.assert_any_call(
                    website, version, new_status, mocker.ANY
                )
    for website, version in [
        (draft_site_to_exclude, VERSION_DRAFT),
        (live_site_excluded, VERSION_LIVE),
    ]:
        with pytest.raises(AssertionError):
            api_mock.get_sync_pipeline.assert_any_call(website)
        with pytest.raises(AssertionError):
            mock_update_status.assert_any_call(website, version, new_status, mocker.ANY)


def test_check_incomplete_publish_build_statuses_abort(settings, api_mock):
    """A website whose publish status has not changed after the cutoff time should be aborted"""
    stuck_website = WebsiteFactory.create(
        draft_publish_status_updated_on=now_in_utc()
        - timedelta(seconds=settings.PUBLISH_STATUS_CUTOFF + 5),
        draft_publish_status=PUBLISH_STATUS_NOT_STARTED,
        latest_build_id_draft=1,
    )
    api_mock.get_sync_pipeline.return_value.get_build_status.return_value = (
        PUBLISH_STATUS_NOT_STARTED
    )
    tasks.check_incomplete_publish_build_statuses.delay()
    api_mock.get_sync_pipeline.return_value.abort_build.assert_called_once_with(
        stuck_website.latest_build_id_draft
    )
    stuck_website.refresh_from_db()
    assert stuck_website.draft_publish_status == PUBLISH_STATUS_ABORTED


def test_check_incomplete_publish_build_statuses_404(settings, mocker, api_mock):
    """A website with a non-existent pipeline/build should have publishing status set to errored"""
    mock_log = mocker.patch("content_sync.tasks.log.error")
    bad_build_website = WebsiteFactory.create(
        draft_publish_status_updated_on=now_in_utc()
        - timedelta(seconds=settings.PUBLISH_STATUS_CUTOFF + 5),
        draft_publish_status=PUBLISH_STATUS_NOT_STARTED,
        latest_build_id_draft=1,
    )
    api_mock.get_sync_pipeline.return_value.get_build_status.side_effect = HTTPError(
        response=mocker.Mock(status_code=404)
    )
    tasks.check_incomplete_publish_build_statuses.delay()
    mock_log.assert_called_once_with(
        "Could not find %s build %s for %s",
        VERSION_DRAFT,
        bad_build_website.latest_build_id_draft,
        bad_build_website.name,
    )
    bad_build_website.refresh_from_db()
    assert bad_build_website.draft_publish_status == PUBLISH_STATUS_ERRORED


def test_check_incomplete_publish_build_statuses_500(settings, mocker, api_mock):
    """An error should be logged and status not updated if querying for the build status returns a non-404 error"""
    mock_log = mocker.patch("content_sync.tasks.log.exception")
    website = WebsiteFactory.create(
        live_publish_status_updated_on=now_in_utc()
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        live_publish_status=PUBLISH_STATUS_NOT_STARTED,
        latest_build_id_live=1,
    )
    api_mock.get_sync_pipeline.return_value.get_build_status.side_effect = HTTPError(
        response=mocker.Mock(status_code=500)
    )
    tasks.check_incomplete_publish_build_statuses.delay()
    mock_log.assert_called_once_with(
        "Error updating publishing status for website %s", website.name
    )
    website.refresh_from_db()
    assert website.live_publish_status == PUBLISH_STATUS_NOT_STARTED
