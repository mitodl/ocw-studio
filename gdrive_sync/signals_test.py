"""gdrive_sync.signals tests"""

import pytest

from gdrive_sync.factories import DriveFileFactory


@pytest.mark.django_db()
def test_delete_from_s3(mocker):
    """Deleting a DriveFile should also delete it from S3"""
    mock_delete_s3_objects = mocker.patch("gdrive_sync.signals.delete_s3_objects")
    drive_file = DriveFileFactory.create()
    drive_file.delete()
    mock_delete_s3_objects.delay.assert_called_once_with(drive_file.s3_key)
