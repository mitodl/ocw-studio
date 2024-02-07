"""
Tests for the backfill_gdrive_folder management command.

The command is tested under two conditions:
1. When the Google Drive folder for a course site is empty.
2. When the Google Drive folder already has content.

In the first case, the command should download files from course's S3 bucket for all course resources
and upload them to its Google Drive folder.

In the second case, the command should do nothing.
"""

import pytest
from django.core.management import call_command

from gdrive_sync.constants import DRIVE_MIMETYPE_FOLDER
from gdrive_sync.models import DriveFile
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(params=[True, False])
def mock_get_drive_service(request, mocker):
    """Mock Google Drive service"""
    return_empty_files = request.param
    mock_gdrive_service = mocker.Mock()

    if return_empty_files:
        mock_gdrive_service.files().create().execute.return_value = {"id": "test_id"}

        mock_gdrive_service.files().get().execute.return_value = {
            "id": "test_id",
            "md5Checksum": "test_checksum",
            "webContentLink": "test_link",
        }
        mock_gdrive_service.files().list().execute.return_value = {
            "files": [],
            "nextPageToken": None,
        }
    else:
        mock_gdrive_service.files().list().execute.return_value = {
            "files": [{"id": "test_id", "mimeType": "text/plain"}],
            "nextPageToken": None,
        }
    return (
        mocker.patch(
            "gdrive_sync.api.get_drive_service", return_value=mock_gdrive_service
        ),
        return_empty_files,
    )


@pytest.fixture()
def mock_get_boto3_client(mocker):
    """Mock S3 client"""
    return mocker.patch("main.s3_utils.get_boto3_client")


def test_backfill_gdrive_folder(
    mocker, mock_get_drive_service, mock_get_boto3_client, settings
):
    """Tests that backfill is performed and DriveFile is properly created when the Google Drive folder is empty
    or that backfill is not performed if the Google Drive folder already has content
    """
    mock_s3 = mock_get_boto3_client.return_value
    mock_get_drive_service, return_empty_files = mock_get_drive_service
    mock_gdrive_service = mock_get_drive_service.return_value

    mocker.patch(
        "gdrive_sync.api.query_files",
        return_value=[{"id": "test_folder", "mimeType": DRIVE_MIMETYPE_FOLDER}],
    )
    if return_empty_files:
        mocker.patch(
            "gdrive_sync.management.commands.backfill_gdrive_folder.walk_gdrive_folder",
            return_value=[],
        )
    else:
        mocker.patch(
            "gdrive_sync.management.commands.backfill_gdrive_folder.walk_gdrive_folder",
            return_value=[{"id": "test_file"}],
        )

    website = WebsiteFactory.create(
        name="Test Site", short_id="test-site", gdrive_folder="test_folder"
    )

    resource = WebsiteContentFactory.create(
        website=website,
        title="test.txt",
        type="resource",
        file="/test_path/test_file",
        metadata={
            "file_type": "text/plain",
            "title": "test.txt",
            "resourcetype": "Document",
        },
    )
    call_command("backfill_gdrive_folder", filter="test-site")
    if return_empty_files:
        mock_s3.download_fileobj.assert_called_with(
            settings.AWS_STORAGE_BUCKET_NAME, str(resource.file).lstrip("/"), mocker.ANY
        )
        mock_gdrive_service.files().create.assert_called_with(
            body=mocker.ANY, media_body=mocker.ANY, fields="id", supportsAllDrives=True
        )
        drive_file = DriveFile.objects.get(file_id="test_id")
        assert drive_file.checksum == "test_checksum"
        assert drive_file.name == "test.txt"
        assert drive_file.mime_type == "text/plain"
        assert drive_file.resource == resource
    else:
        mock_s3.download_fileobj.assert_not_called()
        mock_gdrive_service.files().create.assert_not_called()
