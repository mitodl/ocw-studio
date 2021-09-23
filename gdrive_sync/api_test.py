"""gdrive_sync.api tests"""
import json

import pytest
from moto import mock_s3
from requests import HTTPError

from gdrive_sync import api
from gdrive_sync.api import get_resource_type
from gdrive_sync.conftest import LIST_VIDEO_RESPONSES
from gdrive_sync.constants import (
    DRIVE_FOLDER_FILES,
    DRIVE_FOLDER_VIDEOS,
    DriveFileStatus,
)
from gdrive_sync.factories import DriveFileFactory
from main.s3_utils import get_s3_resource
from websites.constants import (
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_OTHER,
    RESOURCE_TYPE_VIDEO,
)


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name, too-many-arguments


@pytest.fixture
def mock_service(mocker):
    """Mock google drive service """
    return mocker.patch("gdrive_sync.api.get_drive_service")


def test_get_drive_service(settings, mocker):
    """get_drive_service should return a functional google resource"""
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = '{"credentials": "data"}'
    mock_credentials = mocker.patch("gdrive_sync.api.ServiceAccountCredentials")
    service = api.get_drive_service()
    mock_credentials.from_service_account_info.assert_called_once_with(
        json.loads(settings.DRIVE_SERVICE_ACCOUNT_CREDS),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    assert service.files() is not None


@pytest.mark.parametrize("drive_id", [None, "testDrive"])
def test_get_file_list(settings, mock_service, drive_id):
    """get_file_list should return expected results"""
    settings.DRIVE_SHARED_ID = drive_id
    query = "(mimeType contains 'video/')"

    mock_list = mock_service.return_value.files.return_value.list
    mock_execute = mock_list.return_value.execute
    mock_execute.side_effect = LIST_VIDEO_RESPONSES
    fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"

    drive_kwargs = {"driveId": drive_id, "corpora": "drive"} if drive_id else {}
    query_kwargs = {"q": query} if query else {}
    extra_kwargs = {**drive_kwargs, **query_kwargs}
    files = api.get_file_list(query=query, fields=fields)
    assert files == LIST_VIDEO_RESPONSES[0]["files"] + LIST_VIDEO_RESPONSES[1]["files"]
    assert mock_execute.call_count == 2
    expected_kwargs = {
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "fields": fields,
        **extra_kwargs,
    }
    mock_list.assert_any_call(**expected_kwargs)
    mock_list.assert_any_call(
        pageToken=LIST_VIDEO_RESPONSES[0]["nextPageToken"], **expected_kwargs
    )


def test_get_parent_tree(mock_service):
    """get_parent_tree should return expected dict values"""
    mock_execute = mock_service.return_value.files.return_value.get.return_value.execute
    mock_execute.side_effect = [
        {"id": "3N", "name": "final", "parents": ["2N"]},
        {"id": "2N", "name": "semifinal", "parents": ["1N"]},
        {"id": "1N", "name": "drive", "parents": []},
    ]
    assert api.get_parent_tree(["3N"]) == [
        {"id": "2N", "name": "semifinal"},
        {"id": "3N", "name": "final"},
    ]


def test_stream_to_s3(settings, mocker):
    """stream_to_s3 should make expected drive api and S3 upload calls"""
    mock_service = mocker.patch("gdrive_sync.api.get_drive_service")
    mock_download = mocker.patch("gdrive_sync.api.streaming_download")
    mock_boto3 = mocker.patch("gdrive_sync.api.boto3")
    mock_bucket = mock_boto3.resource.return_value.Bucket.return_value
    drive_file = DriveFileFactory.create()
    api.stream_to_s3(drive_file)
    mock_service.return_value.permissions.return_value.create.assert_called_once()
    key = f"{settings.DRIVE_S3_UPLOAD_PREFIX}/{drive_file.website.short_id}/{drive_file.file_id}/{drive_file.name}"
    mock_bucket.upload_fileobj.assert_called_with(
        Fileobj=mocker.ANY,
        Key=key,
        ExtraArgs={"ContentType": drive_file.mime_type, "ACL": "public-read"},
    )
    mock_download.assert_called_once_with(drive_file)
    mock_service.return_value.permissions.return_value.delete.assert_called_once()
    drive_file.refresh_from_db()
    assert drive_file.status == DriveFileStatus.UPLOAD_COMPLETE


@pytest.mark.django_db
def test_stream_to_s3_error(mocker):
    """Task should make expected drive api and S3 upload calls"""
    mocker.patch("gdrive_sync.api.boto3")
    mock_service = mocker.patch("gdrive_sync.api.get_drive_service")
    mocker.patch("gdrive_sync.api.streaming_download", side_effect=HTTPError())
    drive_file = DriveFileFactory.create()
    with pytest.raises(HTTPError):
        api.stream_to_s3(drive_file)
    drive_file.refresh_from_db()
    assert drive_file.status == DriveFileStatus.UPLOAD_FAILED
    mock_service.return_value.permissions.return_value.delete.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "parent_folder,parent_folder_in_ancestors",
    [(None, False), ("correct_parent", False), ("correct_parent", True)],
)
@pytest.mark.parametrize("folder_exists", [True, False])
def test_create_gdrive_folders(  # pylint:disable=too-many-locals,too-many-arguments
    settings,
    mocker,
    parent_folder,
    parent_folder_in_ancestors,
    folder_exists,
    mock_service,
):
    """Task should make expected drive api and S3 upload calls"""
    website_short_id = "short_id"
    site_folder_id = "SiteFolderID"

    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = parent_folder

    if folder_exists:
        existing_list_response = [{"id": site_folder_id, "parents": ["first_parent"]}]
    else:
        existing_list_response = []

    mock_list_files = mocker.patch(
        "gdrive_sync.api.get_file_list", side_effect=[existing_list_response, [], []]
    )

    if parent_folder_in_ancestors:
        get_parent_tree_response = [{"id": "correct_parent"}, {"id": "first_parent"}]
    else:
        get_parent_tree_response = [{"id": "first_parent"}]

    mock_get_parent_tree = mocker.patch(
        "gdrive_sync.api.get_parent_tree",
        return_value=get_parent_tree_response,
    )

    base_query = "mimeType = 'application/vnd.google-apps.folder' and not trashed and "
    expected_folder_query = f"{base_query}name = '{website_short_id}'"
    expected_fields = "nextPageToken, files(id, name, parents)"

    mock_create = mock_service.return_value.files.return_value.create
    mock_execute = mock_create.return_value.execute
    mock_execute.side_effect = [{"id": site_folder_id}, {"id": "sub1"}, {"id": "sub2"}]

    api.create_gdrive_folders(website_short_id=website_short_id)

    mock_list_files.assert_any_call(query=expected_folder_query, fields=expected_fields)

    if folder_exists and parent_folder:
        mock_get_parent_tree.assert_called_once_with(["first_parent"])
    else:
        mock_get_parent_tree.assert_not_called()

    if not folder_exists or (parent_folder and not parent_folder_in_ancestors):
        expected_file_metadata = {
            "name": website_short_id,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_folder:
            expected_file_metadata["parents"] = [parent_folder]
        else:
            expected_file_metadata["parents"] = ["test_drive"]

        mock_create.assert_any_call(
            supportsAllDrives=True, body=expected_file_metadata, fields="id"
        )

    for subfolder in [DRIVE_FOLDER_FILES, DRIVE_FOLDER_VIDEOS]:
        expected_folder_query = (
            f"{base_query}name = '{subfolder}' and parents = '{site_folder_id}'"
        )
        expected_file_metadata = {
            "name": subfolder,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [site_folder_id],
        }
        mock_list_files.assert_any_call(
            query=expected_folder_query, fields=expected_fields
        )
        mock_create.assert_any_call(
            supportsAllDrives=True, body=expected_file_metadata, fields="id"
        )


@mock_s3
@pytest.mark.parametrize(
    "filename, mimetype, expected_type",
    [
        ["file.docx", "application/ms-word", RESOURCE_TYPE_DOCUMENT],
        ["file.html", "text/html", RESOURCE_TYPE_DOCUMENT],
        ["file.mp4", "video/mp4", RESOURCE_TYPE_VIDEO],
        ["file.jpeg", "image/jpeg", RESOURCE_TYPE_IMAGE],
        ["file.py", "application/python", RESOURCE_TYPE_OTHER],
    ],
)
def test_get_resource_type(settings, filename, mimetype, expected_type) -> str:
    """get_resource_type should return the expected value for an S3 object"""
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"
    settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
    conn = get_s3_resource()
    conn.create_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
    test_bucket = conn.Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)
    test_bucket.objects.all().delete()
    test_bucket.put_object(Key=filename, Body=b"", ContentType=mimetype)
    assert get_resource_type(filename) == expected_type
