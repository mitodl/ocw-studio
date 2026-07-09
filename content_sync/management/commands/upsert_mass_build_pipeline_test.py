"""Tests for the upsert_mass_build_pipeline management command"""  # noqa: INP001

import pytest
from django.core.management import CommandError, call_command

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_get_pipeline(mocker, settings):
    """Mock the pipeline factory used by the command and enable the pipeline backend"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    return mocker.patch(
        "content_sync.management.commands.upsert_mass_build_pipeline.get_mass_build_sites_pipeline"
    )


def test_sync_with_delete_and_offline_raises(mock_get_pipeline):
    """--sync-with-delete combined with --offline should raise without upserting"""
    with pytest.raises(CommandError, match="cannot be combined with --offline"):
        call_command("upsert_mass_build_pipeline", sync_with_delete=True, offline=True)
    mock_get_pipeline.assert_not_called()


def test_sync_with_delete_and_unpause_raises(mock_get_pipeline):
    """--sync-with-delete combined with --unpause should raise without upserting"""
    with pytest.raises(CommandError, match="cannot be combined with --unpause"):
        call_command("upsert_mass_build_pipeline", sync_with_delete=True, unpause=True)
    mock_get_pipeline.assert_not_called()


def test_sync_with_delete_upserts_both_versions_unpaused(mock_get_pipeline):
    """--sync-with-delete alone should upsert draft and live destructive instances and never unpause them"""
    call_command("upsert_mass_build_pipeline", sync_with_delete=True)

    assert mock_get_pipeline.call_count == 2
    for call in mock_get_pipeline.call_args_list:
        assert call.kwargs["sync_with_delete"] is True
    called_versions = {call.args[0] for call in mock_get_pipeline.call_args_list}
    assert called_versions == {VERSION_DRAFT, VERSION_LIVE}

    pipeline = mock_get_pipeline.return_value
    assert pipeline.upsert_pipeline.call_count == 2
    pipeline.unpause.assert_not_called()


def test_default_invocation_does_not_use_sync_with_delete(mock_get_pipeline):
    """A plain invocation should upsert the default (non-destructive) instances"""
    call_command("upsert_mass_build_pipeline")

    assert mock_get_pipeline.call_count == 2
    for call in mock_get_pipeline.call_args_list:
        assert call.kwargs["sync_with_delete"] is False

    pipeline = mock_get_pipeline.return_value
    pipeline.unpause.assert_not_called()


def test_unpause_without_sync_with_delete_still_works(mock_get_pipeline):
    """--unpause alone (no --sync-with-delete) should still unpause both instances"""
    call_command("upsert_mass_build_pipeline", unpause=True)

    pipeline = mock_get_pipeline.return_value
    assert pipeline.unpause.call_count == 2


def test_pipeline_backend_not_configured(mocker, settings):
    """The command should exit early if the pipeline backend is not configured"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = None
    mock_get_pipeline = mocker.patch(
        "content_sync.management.commands.upsert_mass_build_pipeline.get_mass_build_sites_pipeline"
    )

    call_command("upsert_mass_build_pipeline", sync_with_delete=True)

    mock_get_pipeline.assert_not_called()


def test_delete_all_deletes_every_mass_build_instance(mock_get_pipeline, mocker):
    """--delete-all should delete all mass-build-sites instances before upserting"""
    mock_pipeline_api = mocker.patch(
        "content_sync.management.commands.upsert_mass_build_pipeline.get_pipeline_api"
    )

    call_command("upsert_mass_build_pipeline", delete_all=True)

    mock_pipeline_api.return_value.delete_pipelines.assert_called_once()
    assert mock_get_pipeline.call_count == 2
