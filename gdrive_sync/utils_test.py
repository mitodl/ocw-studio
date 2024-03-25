"""gdrive_sync.utils tests"""

import pytest
from django.core.files import File
from moto import mock_s3

from gdrive_sync.conftest import setup_s3_test_file_bucket
from gdrive_sync.factories import DriveFileFactory
from gdrive_sync.utils import fetch_content_file_size, fetch_drive_file_size
from websites.factories import WebsiteContentFactory

pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name, too-many-arguments, unused-argument, protected-access


@mock_s3
def test_fetch_drive_file_size_with_key(settings):
    """fetch_drive_file_size should return file size on s3."""
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"
    FILE_KEY = "abc.txt"

    bucket = setup_s3_test_file_bucket(settings, FILE_KEY)

    drive_file = DriveFileFactory.create(s3_key=FILE_KEY)

    result = fetch_drive_file_size(drive_file, bucket)
    assert result == bucket.Object(FILE_KEY).content_length


def test_fetch_drive_file_size_without_key(mocker):
    """fetch_drive_file_size should return None when no file is associated with the object."""
    drive_file = DriveFileFactory.create(s3_key=None)
    result = fetch_drive_file_size(drive_file, mocker.Mock())
    assert result is None


@mock_s3
def test_fetch_content_file_size_from_s3(settings):
    """fetch_content_file_size should return file size on s3 for content."""
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"
    FILE_KEY = "abc.txt"

    bucket = setup_s3_test_file_bucket(settings, FILE_KEY)

    contents = [
        WebsiteContentFactory.create(),
        WebsiteContentFactory.create(metadata={"file": FILE_KEY}),
        WebsiteContentFactory.create(metadata={"file_location": FILE_KEY}),
    ]
    contents[0].file = File(bucket.Object(FILE_KEY), name=FILE_KEY)

    for content in contents:
        result = fetch_content_file_size(content, bucket)
        assert result == bucket.Object(FILE_KEY).content_length


def test_fetch_content_file_size_from_video_archive_url(mocker):
    """
    fetch_content_file_size should return http response length for
    video with archive url but no file association.
    """
    archive_url = "https://www.example.com/video_url"
    content = WebsiteContentFactory.create(
        metadata={"video_files": {"archive_url": archive_url}}
    )

    mock_request = mocker.patch("requests.request")
    mock_request.return_value.status_code = 200
    mock_request.return_value.headers = {"Content-Length": 12345}

    result = fetch_content_file_size(content, mocker.Mock)

    assert archive_url in mock_request.call_args[0]
    assert result == 12345


def test_fetch_content_file_size_no_file(mocker):
    """fetch_content_file_size should return None when no file is present."""
    content = WebsiteContentFactory.create()
    result = fetch_content_file_size(content, mocker.Mock)
    assert result is None
