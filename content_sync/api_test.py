""" Content sync api tests """
from types import SimpleNamespace

import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals
from mitol.common.utils import now_in_utc

from content_sync import api
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from websites.constants import PUBLISH_STATUS_NOT_STARTED
from websites.factories import WebsiteContentFactory, WebsiteFactory


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name


@pytest.fixture()
def mock_api_funcs(settings, mocker):
    """Mock functions used in publish_websites"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    return SimpleNamespace(
        mock_get_backend=mocker.patch("content_sync.api.get_sync_backend"),
        mock_get_pipeline=mocker.patch("content_sync.api.get_sync_pipeline"),
        mock_import_string=mocker.patch("content_sync.api.import_string"),
    )


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
    """ Verify sync_content runs if sync is enabled """
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
    """ Verify sync_content doesn't run anything if sync is disabled """
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


def test_trigger_publish_draft(settings, mocker):
    """Verify preview_website calls the appropriate task"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mock_task = mocker.patch("content_sync.tasks.publish_website_backend_draft")
    website = WebsiteFactory.create()
    api.trigger_publish(website.name, VERSION_DRAFT)
    mock_task.delay.assert_called_once_with(website.name)


def test_trigger_publish_live(settings, mocker):
    """Verify publish_website calls the appropriate task"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.SampleBackend"
    mock_task = mocker.patch("content_sync.tasks.publish_website_backend_live")
    website = WebsiteFactory.create()
    api.trigger_publish(website.name, VERSION_LIVE)
    mock_task.delay.assert_called_once_with(website.name)


def test_sync_github_website_starters(mocker):
    """ Sync website starters from github """
    mock_task = mocker.patch("content_sync.api.tasks.sync_github_site_configs.delay")
    args = "https://github.com/testorg/testconfigs", ["site1/studio.yaml"]
    kwargs = {"commit": "abc123"}
    api.sync_github_website_starters(*args, **kwargs)
    mock_task.assert_called_once_with(*args, **kwargs)


@pytest.mark.parametrize("pipeline_api", [None, {}])
def test_get_sync_pipeline(settings, mocker, pipeline_api):
    """ Verify that get_sync_pipeline() imports the pipeline class based on settings.py """
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    import_string_mock = mocker.patch("content_sync.pipelines.concourse.SitePipeline")
    website = WebsiteFactory.create()
    api.get_sync_pipeline(website, api=pipeline_api)
    import_string_mock.assert_any_call(website, api=pipeline_api)


def test_create_website_publishing_pipeline(settings, mocker):
    """upsert_website_publishing_pipeline task should be called if pipelines are enabled"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    mock_task = mocker.patch(
        "content_sync.api.tasks.upsert_website_publishing_pipeline.delay"
    )
    website = WebsiteFactory.create()
    api.create_website_publishing_pipeline(website)
    mock_task.assert_called_once_with(website.name)


def test_create_website_publishing_pipeline_disabled(settings, mocker):
    """upsert_website_publishing_pipeline task should not be called if pipelines are disabled"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = None
    mock_task = mocker.patch(
        "content_sync.api.tasks.upsert_website_publishing_pipeline.delay"
    )
    website = WebsiteFactory.create()
    api.create_website_publishing_pipeline(website)
    mock_task.assert_not_called()


@pytest.mark.parametrize("prepublish", [True, False])
@pytest.mark.parametrize("prepublish_actions", [[], ["some.Action"]])
@pytest.mark.parametrize("has_api", [True, False])
@pytest.mark.parametrize("version", [VERSION_LIVE, VERSION_DRAFT])
@pytest.mark.parametrize("status", [None, PUBLISH_STATUS_NOT_STARTED])
def test_publish_website(  # pylint:disable=redefined-outer-name,too-many-arguments
    settings,
    mocker,
    mock_api_funcs,
    prepublish,
    prepublish_actions,
    has_api,
    version,
    status,
):
    """Verify that the appropriate backend calls are made by the publish_website function"""
    settings.PREPUBLISH_ACTIONS = prepublish_actions
    website = WebsiteFactory.create()
    setattr(website, f"{version}_publish_status", status)
    if status:
        setattr(website, f"{version}_publish_status_updated_on", now_in_utc())
    website.save()
    build_id = 123456
    pipeline_api = mocker.Mock() if has_api else None
    backend = mock_api_funcs.mock_get_backend.return_value
    pipeline = mock_api_funcs.mock_get_pipeline.return_value
    pipeline.trigger_pipeline_build.return_value = build_id
    api.publish_website(
        website.name, version, pipeline_api=pipeline_api, prepublish=prepublish
    )
    mock_api_funcs.mock_get_backend.assert_called_once_with(website)
    mock_api_funcs.mock_get_pipeline.assert_called_once_with(website, api=pipeline_api)
    backend.sync_all_content_to_backend.assert_called_once()
    if version == VERSION_DRAFT:
        backend.merge_backend_draft.assert_called_once()
    else:
        backend.merge_backend_live.assert_called_once()
    pipeline.trigger_pipeline_build.assert_called_once_with(version)
    pipeline.unpause_pipeline.assert_called_once_with(version)
    website.refresh_from_db()
    assert getattr(website, f"latest_build_id_{version}") == build_id
    assert getattr(website, f"{version}_publish_status") == PUBLISH_STATUS_NOT_STARTED
    assert getattr(website, f"has_unpublished_{version}") is (
        status == PUBLISH_STATUS_NOT_STARTED
    )
    assert getattr(website, f"{version}_last_published_by") is None
    assert getattr(website, f"{version}_publish_status_updated_on") is not None
    if len(prepublish_actions) > 0 and prepublish:
        mock_api_funcs.mock_import_string.assert_any_call("some.Action")
        mock_api_funcs.mock_import_string.return_value.assert_any_call(
            website, version=version
        )


def test_publish_website_error(mock_api_funcs, settings):
    """Verify that the appropriate error handling occurs if publish_website throws an exception"""
    settings.PREPUBLISH_ACTIONS = [["some.Action"]]
    mock_api_funcs.mock_import_string.side_effect = Exception("error")
    website = WebsiteFactory.create()
    with pytest.raises(Exception):
        api.publish_website(website.name, VERSION_LIVE)
    mock_api_funcs.mock_get_backend.assert_not_called()


def test_get_mass_publish_pipeline(settings):
    """get_mass_publish_pipeline should return None if no backend is specified"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = None
    assert api.get_mass_publish_pipeline(VERSION_DRAFT) is None
