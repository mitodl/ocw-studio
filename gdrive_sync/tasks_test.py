"""Tests for gdrive_sync tasks"""
import pytest

from gdrive_sync import tasks
from gdrive_sync.factories import DriveFileFactory


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_import_gdrive_videos(settings, mocker, shared_id, drive_creds):
    """ Videos should be imported only if required settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_import = mocker.patch("gdrive_sync.tasks.api.import_recent_videos")
    tasks.import_gdrive_videos()
    assert mock_import.call_count == (1 if shared_id and drive_creds else 0)


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_stream_drive_file_to_s3(settings, mocker, shared_id, drive_creds):
    """ File should be streamed only if required settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_stream = mocker.patch("gdrive_sync.tasks.api.stream_to_s3")
    drive_file = DriveFileFactory.create()
    tasks.stream_drive_file_to_s3(drive_file.file_id)
    assert mock_stream.call_count == (1 if shared_id and drive_creds else 0)


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_create_gdrive_folder_if_not_exists(settings, mocker, shared_id, drive_creds):
    """ Folder should be created if settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_create_folder = mocker.patch(
        "gdrive_sync.tasks.api.create_gdrive_folder_if_not_exists"
    )
    tasks.create_gdrive_folder_if_not_exists("test", "test")
    assert mock_create_folder.call_count == (1 if shared_id and drive_creds else 0)
