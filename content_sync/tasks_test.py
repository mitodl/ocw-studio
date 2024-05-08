"""Content sync task tests"""
import os
from datetime import timedelta

import factory
import pytest
import pytz
from django.db.models.signals import post_save
from factory.django import mute_signals
from github.GithubException import RateLimitExceededException
from mitol.common.utils import now_in_utc
from moto import mock_s3
from pytest import fixture  # noqa: PT013
from requests import HTTPError

from content_sync import tasks
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.factories import ContentSyncStateFactory
from content_sync.pipelines.base import (
    BaseMassBuildSitesPipeline,
    BaseThemeAssetsPipeline,
    BaseUnpublishedSiteRemovalPipeline,
)
from main.s3_utils import get_boto3_resource
from websites.constants import (
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_STARTED,
    PUBLISH_STATUS_SUCCEEDED,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent

pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@fixture()
def api_mock(mocker, settings):
    """Return a mocked content_sync.tasks.api, and set the backend"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    return mocker.patch("content_sync.tasks.api")


@fixture()
def log_mock(mocker):
    """Return a mocked log object"""
    return mocker.patch("content_sync.tasks.log")


def test_sync_content(api_mock, log_mock):
    """Verify the sync_content task calls the corresponding API method"""
    sync_state = ContentSyncStateFactory.create()
    tasks.sync_content.delay(sync_state.id)

    log_mock.debug.assert_not_called()
    api_mock.sync_content.assert_called_once_with(sync_state)


def test_sync_content_not_exists(api_mock, log_mock):
    """Verify the sync_content task does not call the corresponding API method"""
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
    """Verify the create_website_backend task does not call API and backend methods"""
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


def test_update_mass_build_pipelines(api_mock):
    """Verify that mass_build_sites pipelines are upserted under the proper conditions"""
    website = WebsiteFactory.create()
    fake_date = factory.Faker("date_time", tzinfo=pytz.utc)
    website.draft_publish_date = None
    website.publish_date = None
    tasks.update_mass_build_pipelines_on_publish(version=VERSION_DRAFT, website=website)
    api_mock.get_mass_build_sites_pipeline.assert_any_call(VERSION_DRAFT)
    api_mock.get_mass_build_sites_pipeline.assert_any_call(VERSION_DRAFT, offline=True)
    assert api_mock.get_mass_build_sites_pipeline.call_count == 2
    website.draft_publish_date = fake_date
    tasks.update_mass_build_pipelines_on_publish(version=VERSION_DRAFT, website=website)
    assert api_mock.get_mass_build_sites_pipeline.call_count == 2
    tasks.update_mass_build_pipelines_on_publish(version=VERSION_LIVE, website=website)
    api_mock.get_mass_build_sites_pipeline.assert_any_call(VERSION_LIVE)
    api_mock.get_mass_build_sites_pipeline.assert_any_call(VERSION_LIVE, offline=True)
    assert api_mock.get_mass_build_sites_pipeline.call_count == 4
    website.publish_date = fake_date
    tasks.update_mass_build_pipelines_on_publish(version=VERSION_LIVE, website=website)
    assert api_mock.get_mass_build_sites_pipeline.call_count == 4
    website.unpublish_status = PUBLISH_STATUS_NOT_STARTED
    tasks.update_mass_build_pipelines_on_publish(version=VERSION_DRAFT, website=website)
    tasks.update_mass_build_pipelines_on_publish(version=VERSION_LIVE, website=website)
    assert api_mock.get_mass_build_sites_pipeline.call_count == 8


@pytest.mark.parametrize("backend_exists", [True, False])
@pytest.mark.parametrize("create_backend", [True, False])
@pytest.mark.parametrize("delete", [True, False])
def test_sync_unsynced_websites(api_mock, backend_exists, create_backend, delete):
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

    tasks.sync_unsynced_websites.delay(create_backends=create_backend, delete=delete)
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
    assert (
        api_mock.get_sync_backend.return_value.delete_orphaned_content_in_backend.call_count
        == (2 if delete and (create_backend or backend_exists) else 0)
    )


@pytest.mark.parametrize("check_limit", [True, False])
def test_sync_all_websites_rate_limit_low(mocker, settings, check_limit):
    """Test that sync_unsynced_websites pauses if the GithubBackend is close to exceeding rate limit"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    settings.GITHUB_RATE_LIMIT_CHECK = check_limit
    sleep_mock = mocker.patch("content_sync.api.sleep")
    mock_git_wrapper = mocker.patch("content_sync.backends.github.GithubApiWrapper")
    mock_dt_now = mocker.patch(
        "content_sync.tasks.now_in_utc", return_value=now_in_utc()
    )
    mock_git_wrapper.return_value.git.rate_limiting = (
        5,
        mock_dt_now + timedelta(seconds=1000),
    )
    ContentSyncStateFactory.create_batch(2)
    tasks.sync_unsynced_websites.delay()
    assert sleep_mock.call_count == (2 if check_limit else 0)


@pytest.mark.parametrize(
    ("calls_left", "use_default_sleep"), [[5, False], [5000, True]]  # noqa: PT007
)
def test_sync_all_websites_rate_limit_sleep_length(
    mocker, settings, calls_left, use_default_sleep
):
    """Test that sync_unsynced_websites pauses if the GithubBackend is close to exceeding rate limit"""
    settings.GITHUB_RATE_LIMIT_MIN_SLEEP = 12
    settings.GITHUB_RATE_LIMIT_CHECK = True
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    sleep_mock = mocker.patch("content_sync.api.sleep")
    mock_git_wrapper = mocker.patch("content_sync.backends.github.GithubApiWrapper")
    mock_dt_now = mocker.patch(
        "content_sync.tasks.now_in_utc", return_value=now_in_utc()
    )
    mock_git_wrapper.return_value.git.rate_limiting = (
        calls_left,
        mock_dt_now + timedelta(seconds=1000),
    )
    ContentSyncStateFactory.create_batch(2)
    tasks.sync_unsynced_websites.delay()
    if use_default_sleep:
        sleep_mock.assert_any_call(12)
    else:
        assert sleep_mock.call_args_list[0][0][0] > 12


def test_sync_all_websites_rate_limit_exceeded(settings, api_mock):
    """Test that sync_unsynced_websites halts if instantiating a GithubBackend exceeds the rate limit"""
    settings.GITHUB_RATE_LIMIT_CHECK = True
    api_mock.get_sync_backend.side_effect = RateLimitExceededException(
        status=403, data={}, headers={}
    )
    ContentSyncStateFactory.create_batch(2)
    with pytest.raises(RateLimitExceededException):
        tasks.sync_unsynced_websites.delay()
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_not_called()


def test_publish_website_backend_draft(api_mock):
    """Verify that the appropriate backend calls are made by the publish_website_backend_draft task"""
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
    """sync_github_site_configs should call apis.github.sync_starter_configs with same args, kwargs"""
    mock_git = mocker.patch("content_sync.tasks.github")
    args = "https://github.com/testorg/testconfigs", ["site1/studio.yaml"]
    kwargs = {"commit": "abc123"}
    tasks.sync_github_site_configs.delay(*args, **kwargs)
    mock_git.sync_starter_configs.assert_called_once_with(*args, **kwargs)


def test_upsert_web_publishing_pipeline(api_mock):
    """upsert_web_publishing_pipeline should call api.get_site_pipeline"""
    website = WebsiteFactory.create()
    tasks.upsert_website_publishing_pipeline.delay(website.name)
    api_mock.get_site_pipeline.assert_called_once_with(website)


def test_upsert_web_publishing_pipeline_missing(api_mock, log_mock):
    """upsert_web_publishing_pipeline should log a debug message if the website doesn't exist"""
    tasks.upsert_website_publishing_pipeline.delay("fake")
    log_mock.debug.assert_called_once_with(
        "Attempted to create pipeline for Website that doesn't exist: name=%s",
        "fake",
    )
    api_mock.get_site_pipeline.assert_not_called()


@pytest.mark.parametrize("create_backend", [True, False])
@pytest.mark.parametrize("unpause", [True, False])
@pytest.mark.parametrize("hugo_args", [None, "--baseURL /"])
@pytest.mark.parametrize(("chunk_size", "chunks"), [[3, 1], [2, 2]])  # noqa: PT007
def test_upsert_pipelines(  # pylint:disable=too-many-arguments, unused-argument  # noqa: PLR0913
    mocker, mocked_celery, create_backend, unpause, hugo_args, chunk_size, chunks
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
            hugo_args=hugo_args,
            chunk_size=chunk_size,
        )
    mock_batch.assert_any_call(
        website_names[0:chunk_size],
        create_backend=create_backend,
        unpause=unpause,
        hugo_args=hugo_args,
    )
    if chunks > 1:
        mock_batch.assert_any_call(
            website_names[chunk_size:],
            create_backend=create_backend,
            unpause=unpause,
            hugo_args=hugo_args,
        )


@pytest.mark.parametrize("unpause", [True, False])
def test_upsert_theme_assets_pipeline(  # pylint:disable=unused-argument
    settings, mocker, mocked_celery, unpause
):
    """Calls upsert_theme_assets_pipeline and unpauses if asked"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    mocker.patch("content_sync.pipelines.concourse.PipelineApi.auth")
    mock_pipeline_unpause = mocker.patch(
        "content_sync.pipelines.concourse.ThemeAssetsPipeline.unpause_pipeline"
    )
    mock_upsert_pipeline = mocker.patch(
        "content_sync.pipelines.concourse.ThemeAssetsPipeline.upsert_pipeline",
    )
    tasks.upsert_theme_assets_pipeline(unpause=unpause)
    mock_upsert_pipeline.assert_called_once()
    if unpause:
        mock_pipeline_unpause.assert_called_once_with(
            BaseThemeAssetsPipeline.PIPELINE_NAME
        )
    else:
        mock_pipeline_unpause.assert_not_called()


@pytest.mark.parametrize("create_backend", [True, False])
@pytest.mark.parametrize("unpause", [True, False])
@pytest.mark.parametrize("hugo_args", [None, "--baseURL /"])
@pytest.mark.parametrize("check_limit", [True, False])
def test_upsert_website_pipeline_batch(  # pylint:disable=too-many-arguments  # noqa: PLR0913
    mocker, settings, create_backend, unpause, hugo_args, check_limit
):
    """upsert_website_pipeline_batch should make the expected function calls"""
    settings.GITHUB_RATE_LIMIT_CHECK = check_limit
    mock_get_backend = mocker.patch("content_sync.tasks.api.get_sync_backend")
    mock_get_pipeline = mocker.patch("content_sync.tasks.api.get_site_pipeline")
    mock_throttle = mocker.patch("content_sync.tasks.api.throttle_git_backend_calls")
    websites = WebsiteFactory.create_batch(2)
    website_names = sorted([website.name for website in websites])
    tasks.upsert_website_pipeline_batch(
        website_names,
        create_backend=create_backend,
        unpause=unpause,
        hugo_args=hugo_args,
    )
    mock_get_pipeline.assert_any_call(websites[0], hugo_args=hugo_args, api=None)
    mock_get_pipeline.assert_any_call(websites[1], hugo_args=hugo_args, api=mocker.ANY)
    if create_backend:
        for website in websites:
            mock_get_backend.assert_any_call(website)
        mock_throttle.assert_any_call(mock_get_backend.return_value)
        mock_backend = mock_get_backend.return_value
        assert mock_backend.create_website_in_backend.call_count == 2
        assert mock_backend.sync_all_content_to_backend.call_count == 2
    else:
        mock_get_backend.assert_not_called()
    mock_pipeline = mock_get_pipeline.return_value
    assert mock_pipeline.upsert_pipeline.call_count == 2
    if unpause:
        mock_pipeline.unpause_pipeline.assert_any_call(VERSION_DRAFT)
        mock_pipeline.unpause_pipeline.assert_any_call(VERSION_LIVE)
    else:
        mock_pipeline.unpause_pipeline.assert_not_called()


@pytest.mark.parametrize("prepublish", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize(("chunk_size", "chunks"), [[3, 1], [2, 2]])  # noqa: PT007
@pytest.mark.parametrize("has_mass_build", [True, False])
@pytest.mark.parametrize("no_mass_build", [True, False])
def test_publish_websites(  # pylint:disable=unused-argument,too-many-arguments  # noqa: PLR0913
    mocker,
    mocked_celery,
    api_mock,
    version,
    chunk_size,
    chunks,
    prepublish,
    has_mass_build,
    no_mass_build,
):
    """publish_websites calls upsert_pipeline_batch with correct arguments"""
    websites = WebsiteFactory.create_batch(3)
    website_names = sorted([website.name for website in websites])
    mock_batch = mocker.patch("content_sync.tasks.publish_website_batch.s")
    mocker.patch(
        "content_sync.tasks.api.get_mass_build_sites_pipeline",
        return_value=(mocker.Mock() if has_mass_build else None),
    )
    trigger_pipeline = no_mass_build or not has_mass_build
    mock_mass_build = mocker.patch("content_sync.tasks.trigger_mass_build.si")
    with pytest.raises(TabError):
        tasks.publish_websites.delay(
            website_names,
            version,
            chunk_size=chunk_size,
            prepublish=prepublish,
            no_mass_build=no_mass_build,
        )
    mock_batch.assert_any_call(
        website_names[0:chunk_size],
        version,
        prepublish=prepublish,
        trigger_pipeline=trigger_pipeline,
    )
    if chunks > 1:
        mock_batch.assert_any_call(
            website_names[chunk_size:],
            version,
            prepublish=prepublish,
            trigger_pipeline=trigger_pipeline,
        )
    if not trigger_pipeline:
        mock_mass_build.assert_called_once_with(version)
    else:
        mock_mass_build.assert_not_called()


@pytest.mark.parametrize("prepublish", [True, False])
@pytest.mark.parametrize("trigger", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_publish_website_batch(mocker, version, prepublish, trigger):
    """publish_website_batch should make the expected function calls"""
    mock_import_string = mocker.patch("content_sync.tasks.import_string")
    mock_publish_website = mocker.patch("content_sync.api.publish_website")
    mock_throttle = mocker.patch("content_sync.tasks.api.throttle_git_backend_calls")
    website_names = sorted([website.name for website in WebsiteFactory.create_batch(3)])
    expected_api = (
        mock_import_string.return_value.get_api.return_value if trigger else None
    )
    tasks.publish_website_batch(
        website_names, version, prepublish=prepublish, trigger_pipeline=trigger
    )
    for name in website_names:
        mock_publish_website.assert_any_call(
            name,
            version,
            pipeline_api=expected_api,
            prepublish=prepublish,
            trigger_pipeline=trigger,
        )
    assert mock_throttle.call_count == len(website_names)
    assert mock_import_string.call_count == (
        len(website_names) + 1 if trigger else len(website_names)
    )


@pytest.mark.parametrize(
    ("old_status", "new_status", "should_check", "should_update"),
    [
        [PUBLISH_STATUS_SUCCEEDED, None, False, False],  # noqa: PT007
        [PUBLISH_STATUS_NOT_STARTED, PUBLISH_STATUS_STARTED, True, True],  # noqa: PT007
        [  # noqa: PT007
            PUBLISH_STATUS_NOT_STARTED,
            PUBLISH_STATUS_NOT_STARTED,
            True,
            False,
        ],
    ],
)
@pytest.mark.parametrize("pipeline", [None, "concourse"])
def test_check_incomplete_publish_build_statuses(  # noqa: PLR0913
    settings,
    mocker,
    api_mock,
    old_status,
    new_status,
    should_check,
    should_update,
    pipeline,
):  # pylint:disable=too-many-arguments,too-many-locals
    """check_incomplete_publish_build_statuses should update statuses of pipeline builds"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = pipeline
    mock_update_status = mocker.patch("content_sync.tasks.update_website_status")
    now = now_in_utc()
    draft_site_in_query = WebsiteFactory.create(
        draft_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        draft_publish_status=old_status,
        latest_build_id_draft=1,
    )
    draft_site_to_exclude_time = WebsiteFactory.create(
        draft_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME - 5),
        draft_publish_status=old_status,
        latest_build_id_draft=2,
    )
    draft_site_to_exclude_status = WebsiteFactory.create(
        draft_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        draft_publish_status=PUBLISH_STATUS_SUCCEEDED,
        latest_build_id_draft=2,
    )
    live_site_in_query = WebsiteFactory.create(
        live_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        live_publish_status=old_status,
        latest_build_id_live=3,
    )
    live_site_excluded_time = WebsiteFactory.create(
        live_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME - 5),
        live_publish_status=old_status,
        latest_build_id_live=4,
    )
    live_site_excluded_status = WebsiteFactory.create(
        live_publish_status_updated_on=now
        - timedelta(seconds=settings.PUBLISH_STATUS_WAIT_TIME + 5),
        live_publish_status=None,
        latest_build_id_live=4,
    )
    api_mock.get_site_pipeline.return_value.get_build_status.return_value = new_status
    tasks.check_incomplete_publish_build_statuses.delay()
    for website, version in [
        (draft_site_in_query, VERSION_DRAFT),
        (live_site_in_query, VERSION_LIVE),
    ]:
        if should_check and pipeline is not None:
            api_mock.get_site_pipeline.assert_any_call(website)
            api_mock.get_site_pipeline.return_value.get_build_status.assert_any_call(
                getattr(website, f"latest_build_id_{version}")
            )
            if should_update:
                mock_update_status.assert_any_call(
                    website, version, new_status, mocker.ANY
                )
        else:
            with pytest.raises(AssertionError):
                api_mock.get_site_pipeline.assert_any_call(website)
            with pytest.raises(AssertionError):
                mock_update_status.assert_any_call(
                    website, version, new_status, mocker.ANY
                )
    for website, version in [
        (draft_site_to_exclude_time, VERSION_DRAFT),
        (draft_site_to_exclude_status, VERSION_DRAFT),
        (live_site_excluded_time, VERSION_LIVE),
        (live_site_excluded_status, VERSION_LIVE),
    ]:
        with pytest.raises(AssertionError):
            api_mock.get_site_pipeline.assert_any_call(website)
        with pytest.raises(AssertionError):
            mock_update_status.assert_any_call(website, version, new_status, mocker.ANY)


def test_check_incomplete_publish_build_statuses_no_setting(settings, api_mock):
    """Pipeline apis should not be called if settings.CONTENT_SYNC_PIPELINE_BACKEND is not set"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = None
    stuck_website = WebsiteFactory.create(
        draft_publish_status_updated_on=now_in_utc()
        - timedelta(seconds=settings.PUBLISH_STATUS_CUTOFF + 5),
        draft_publish_status=PUBLISH_STATUS_NOT_STARTED,
        latest_build_id_draft=1,
    )
    api_mock.get_site_pipeline.return_value.get_build_status.return_value = (
        PUBLISH_STATUS_NOT_STARTED
    )
    tasks.check_incomplete_publish_build_statuses.delay()
    api_mock.get_site_pipeline.assert_not_called()
    stuck_website.refresh_from_db()
    assert stuck_website.draft_publish_status == PUBLISH_STATUS_NOT_STARTED


def test_check_incomplete_publish_build_statuses_abort(settings, api_mock):
    """A website whose publish status has not changed after the cutoff time should be aborted"""
    stuck_website = WebsiteFactory.create(
        draft_publish_status_updated_on=now_in_utc()
        - timedelta(seconds=settings.PUBLISH_STATUS_CUTOFF + 5),
        draft_publish_status=PUBLISH_STATUS_NOT_STARTED,
        latest_build_id_draft=1,
    )
    api_mock.get_site_pipeline.return_value.get_build_status.return_value = (
        PUBLISH_STATUS_NOT_STARTED
    )
    tasks.check_incomplete_publish_build_statuses.delay()
    api_mock.get_site_pipeline.return_value.abort_build.assert_called_once_with(
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
    api_mock.get_site_pipeline.return_value.get_build_status.side_effect = HTTPError(
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
    api_mock.get_site_pipeline.return_value.get_build_status.side_effect = HTTPError(
        response=mocker.Mock(status_code=500)
    )
    tasks.check_incomplete_publish_build_statuses.delay()
    mock_log.assert_called_once_with(
        "Error updating publishing status for website %s", website.name
    )
    website.refresh_from_db()
    assert website.live_publish_status == PUBLISH_STATUS_NOT_STARTED


@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize("backend", ["concourse", None])
def test_trigger_mass_build(settings, mocker, backend, version):
    """trigger_mass_build should call trigger_pipeline_build if enabled"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = backend
    mocker.patch("content_sync.pipelines.concourse.PipelineApi.auth")
    mock_pipeline_unpause = mocker.patch(
        "content_sync.pipelines.concourse.GeneralPipeline.unpause_pipeline"
    )
    mock_pipeline_trigger = mocker.patch(
        "content_sync.pipelines.concourse.GeneralPipeline.trigger_pipeline_build"
    )
    pipeline_name = BaseMassBuildSitesPipeline.PIPELINE_NAME
    tasks.trigger_mass_build.delay(version)
    if backend == "concourse":
        mock_pipeline_unpause.assert_called_once_with(pipeline_name)
        mock_pipeline_trigger.assert_called_once_with(pipeline_name)
    else:
        mock_pipeline_trigger.assert_not_called()
        mock_pipeline_unpause.assert_not_called()


@pytest.mark.parametrize("backend", ["concourse", None])
def test_trigger_unpublished_removal(settings, mocker, backend):
    """trigger_unpublished_removal should call trigger_pipeline_build if enabled"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = backend
    mocker.patch("content_sync.pipelines.concourse.PipelineApi.auth")
    mock_remove_website_in_root_website = mocker.patch(
        "content_sync.tasks.remove_website_in_root_website"
    )
    mock_pipeline_unpause = mocker.patch(
        "content_sync.pipelines.concourse.BaseUnpublishedSiteRemovalPipeline.unpause_pipeline"
    )
    mock_pipeline_pause = mocker.patch(
        "content_sync.pipelines.concourse.SitePipeline.pause_pipeline"
    )
    mock_pipeline_trigger = mocker.patch(
        "content_sync.pipelines.concourse.BaseUnpublishedSiteRemovalPipeline.trigger_pipeline_build"
    )
    pipeline_name = BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME
    site = WebsiteFactory.create()
    tasks.trigger_unpublished_removal.delay(site.name)
    mock_remove_website_in_root_website.assert_called_once_with(site)
    if backend == "concourse":
        mock_pipeline_pause.assert_called_once_with(VERSION_LIVE)
        mock_pipeline_unpause.assert_called_once_with(pipeline_name)
        mock_pipeline_trigger.assert_called_once_with(pipeline_name)
    else:
        mock_pipeline_trigger.assert_not_called()
        mock_pipeline_unpause.assert_not_called()


def test_update_websites_in_root_website(api_mock):
    """
    The update_websites_in_root_website task should update or create WebsiteContent objects of type website, tied to the root website

    It should not touch websites that have not been published or have been unpublished
    """
    root_website = WebsiteFactory.create(name="ocw-www")
    WebsiteFactory.create_batch(2, draft_publish_date=None, publish_date=None)
    published_sites = WebsiteFactory.create_batch(
        4,
        has_unpublished_live=False,
        has_unpublished_draft=False,
        live_publish_status=PUBLISH_STATUS_SUCCEEDED,
        draft_publish_status=PUBLISH_STATUS_SUCCEEDED,
        latest_build_id_live=1,
        latest_build_id_draft=2,
    )
    unrelated_content = []
    for site in published_sites:
        WebsiteContentFactory.create(website=site, type="sitemetadata")
        unrelated_content.append(
            WebsiteContentFactory.create(website=site, type="page")
        )
    tasks.update_websites_in_root_website()
    website_content = WebsiteContent.objects.filter(
        website=root_website, type="website"
    )
    assert website_content.count() == 4
    api_mock.get_sync_backend.assert_called_once_with(website=root_website)
    mock_backend = api_mock.get_sync_backend.return_value
    upserted_content = mock_backend.sync_all_content_to_backend.call_args[1][
        "query_set"
    ]
    assert set(website_content).difference(set(upserted_content)) == set()


def test_update_website_in_root_website(api_mock, mocker):
    """
    The update_website_in_root_website task should update or create a single WebsiteContent objects of type website, tied to the root website

    It should not touch websites that have not been published or have been unpublished
    """
    root_website = WebsiteFactory.create(name="ocw-www")
    published_site = WebsiteFactory.create(
        name="published-site",
        has_unpublished_live=False,
        has_unpublished_draft=False,
        live_publish_status=PUBLISH_STATUS_SUCCEEDED,
        draft_publish_status=PUBLISH_STATUS_SUCCEEDED,
        latest_build_id_live=1,
        latest_build_id_draft=2,
    )
    unpublished_site = WebsiteFactory.create(name="unpublished-site")
    WebsiteContentFactory.create(website=published_site, type="sitemetadata")
    WebsiteContentFactory.create(website=published_site, type="page")
    # Assume this content has been published for testing purposes
    root_website.has_unpublished_draft = False
    root_website.has_unpublished_live = False
    root_website.save()
    for version in [VERSION_DRAFT, VERSION_LIVE]:
        tasks.update_website_in_root_website(published_site, version)
        tasks.update_website_in_root_website(unpublished_site, version)
    website_content = WebsiteContent.objects.filter(
        website=root_website, type="website"
    )
    assert website_content.count() == 1
    api_mock.get_sync_backend.assert_has_calls([mocker.call(website=root_website)])
    mock_backend = api_mock.get_sync_backend.return_value
    for call in mock_backend.sync_all_content_to_backend.call_args_list:
        content = call[1]["query_set"].first()
        assert content in website_content
    api_mock.publish_website.assert_called_once_with(
        root_website.name, VERSION_DRAFT, trigger_pipeline=False
    )


def test_remove_website_in_root_website(api_mock):
    """
    The remove_website_in_root_website task should remove a single WebsiteContent objects of type website, tied to the root website
    """
    root_website = WebsiteFactory.create(name="ocw-www")
    published_site = WebsiteFactory.create(
        name="published-site",
        has_unpublished_live=False,
        has_unpublished_draft=False,
        live_publish_status=PUBLISH_STATUS_SUCCEEDED,
        draft_publish_status=PUBLISH_STATUS_SUCCEEDED,
        latest_build_id_live=1,
        latest_build_id_draft=2,
    )
    WebsiteContentFactory.create(website=published_site, type="sitemetadata")
    # Assume this content has been published for testing purposes
    root_website.has_unpublished_draft = False
    root_website.has_unpublished_live = False
    root_website.save()
    for version in [VERSION_DRAFT, VERSION_LIVE]:
        tasks.update_website_in_root_website(published_site, version)
    website_content = WebsiteContent.objects.filter(
        website=root_website, type="website"
    )
    assert website_content.count() == 1
    tasks.remove_website_in_root_website(published_site)
    assert website_content.count() == 0
    api_mock.get_sync_backend.assert_any_call(website=root_website)
    api_mock.get_sync_backend.return_value.sync_all_content_to_backend.assert_any_call()


@mock_s3
@pytest.mark.parametrize(
    "prefix", ["a/prefix", "a/prefix/", "/a/prefix", "/a/prefix/", ""]
)
def test_backpopulate_archive_videos_batch(  # pylint:disable=too-many-arguments, too-many-locals
    mocker, settings, prefix
):
    """backpopulate_archive_videos_batch should push up videos to S3"""
    # Fake the s3 settings
    settings.ENVIRONMENT = "test"
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"  # noqa: S105
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"
    settings.PREVIEW_BUCKET_NAME = "preview_bucket"
    settings.PUBLISH_BUCKET_NAME = "publish_bucket"
    settings.OFFLINE_PREVIEW_BUCKET_NAME = "offline_preview_bucket"
    settings.OFFLINE_PUBLISH_BUCKET_NAME = "offline_publish_bucket"
    # Create our fake bucket
    s3 = get_boto3_resource("s3")
    test_bucket_name = "test_bucket"
    s3.create_bucket(Bucket=test_bucket_name)
    test_bucket = s3.Bucket(name=test_bucket_name)
    mock_get_boto_3_resource = mocker.patch("content_sync.tasks.get_boto3_resource")
    mock_s3_resource = mock_get_boto_3_resource.return_value
    # Create mock Websites and WebsiteContent
    websites = WebsiteFactory.create_batch(4)
    website_names = sorted([website.name for website in websites])
    domain_prefixes = [
        "http://archive.org/download/",
        "https://archive.org/download/",
        "http://www.archive.org/download/",
        "https://ia800303.us.archive.org/download/",
    ]
    for index, site in enumerate(websites):
        print(index)  # noqa: T201
        print(domain_prefixes[index])  # noqa: T201
        s3_path = os.path.join(prefix, site.name).lstrip("/")  # noqa: PTH118
        WebsiteContentFactory.create(
            website=site,
            type="resource",
            metadata={
                "video_files": {
                    "archive_url": f"{domain_prefixes[index]}{site.name}/test_video.mp4"
                }
            },
        )
        test_bucket.put_object(Key=f"{s3_path}/test_video.mp4")
    tasks.backpopulate_archive_videos_batch(test_bucket_name, prefix, website_names)
    # Assert that the proper calls were done to copy the video into the various S3 locations
    # mock_get_boto_3_resource.assert_called_once_with("s3")  # noqa: ERA001
    extra_args = {"ACL": "public-read"}
    for site in websites:
        s3_path = os.path.join(prefix, site.name).lstrip("/")  # noqa: PTH118
        source_arg = {
            "Bucket": test_bucket_name,
            "Key": f"{s3_path}/test_video.mp4",
        }
        online_destination_s3_path = os.path.join(  # noqa: PTH118
            site.url_path, "test_video.mp4"
        )  # noqa: PTH118, RUF100
        offline_destination_s3_path = os.path.join(  # noqa: PTH118
            site.url_path, "static_resources", "test_video.mp4"
        )
        mock_s3_resource.meta.client.copy.assert_any_call(
            source_arg,
            settings.AWS_STORAGE_BUCKET_NAME,
            online_destination_s3_path,
            extra_args,
        )
        mock_s3_resource.meta.client.copy.assert_any_call(
            source_arg,
            settings.PREVIEW_BUCKET_NAME,
            online_destination_s3_path,
            extra_args,
        )
        mock_s3_resource.meta.client.copy.assert_any_call(
            source_arg,
            settings.PUBLISH_BUCKET_NAME,
            online_destination_s3_path,
            extra_args,
        )
        mock_s3_resource.meta.client.copy.assert_any_call(
            source_arg,
            settings.OFFLINE_PREVIEW_BUCKET_NAME,
            offline_destination_s3_path,
            extra_args,
        )
        mock_s3_resource.meta.client.copy.assert_any_call(
            source_arg,
            settings.OFFLINE_PUBLISH_BUCKET_NAME,
            offline_destination_s3_path,
            extra_args,
        )


@pytest.mark.parametrize("prefix", ["/a/prefix", ""])
@pytest.mark.parametrize(("chunk_size", "chunks"), [[3, 1], [2, 2]])  # noqa: PT007
def test_backpopulate_archive_videos(  # pylint:disable=too-many-arguments, unused-argument
    mocker, mocked_celery, prefix, chunk_size, chunks
):
    """backpopulate_archive_videos calls backpopulate_archive_videos_batch with correct arguments"""
    test_bucket_name = "test_bucket"
    websites = WebsiteFactory.create_batch(3)
    website_names = sorted([website.name for website in websites])
    mock_batch = mocker.patch("content_sync.tasks.backpopulate_archive_videos_batch.s")
    with pytest.raises(TabError):
        tasks.backpopulate_archive_videos.delay(
            test_bucket_name,
            prefix,
            website_names,
            chunk_size=chunk_size,
        )
    mock_batch.assert_any_call(
        test_bucket_name,
        prefix,
        website_names[0:chunk_size],
    )
    if chunks > 1:
        mock_batch.assert_any_call(
            test_bucket_name,
            prefix,
            website_names[chunk_size:],
        )
