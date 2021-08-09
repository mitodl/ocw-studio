"""gdrive_sync.api tests"""
import json
from datetime import datetime

import pytest
import pytz
from requests import HTTPError

from gdrive_sync import api
from gdrive_sync.constants import DRIVE_API_FILES, DriveFileStatus
from gdrive_sync.factories import DriveApiQueryTrackerFactory, DriveFileFactory
from gdrive_sync.models import DriveFile
from websites.factories import WebsiteFactory


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name

LIST_RESPONSES = [
    {
        "nextPageToken": "~!!~AI9FV7Tc4k5BiAr1Ckwyu",
        "files": [
            {
                "id": "12JCgxaoHrGvd_Vy5grfCTHr",
                "name": "test_video_1.mp4",
                "mimeType": "video/mp4",
                "parents": ["1lSSPf_kx83O0fcmSA9n4-c3dnB"],
                "webContentLink": "https://drive.google.com/uc?id=12JCgxaoHrGvd_Vy5grfCTHr&export=download",
                "createdTime": "2021-07-28T00:06:40.439Z",
                "modifiedTime": "2021-07-29T16:25:19.375Z",
                "md5Checksum": "633410252",
                "trashed": False,
            },
            {
                "id": "1Co1ZE7nodTjCqXuyFl10B38",
                "name": "test_video_2.mp4",
                "mimeType": "video/mp4",
                "parents": ["TepPI157C9za"],
                "webContentLink": "https://drive.google.com/uc?id=1Co1ZE7nodTjCqXuyFl10B38&export=download",
                "createdTime": "2019-08-27T12:51:41.000Z",
                "modifiedTime": "2021-07-29T16:25:19.187Z",
                "md5Checksum": "3827293107",
                "trashed": False,
            },
        ],
    },
    {
        "files": [
            {
                "id": "Vy5grfCTHr_12JCgxaoHrGvd",
                "name": "test_video_1.mp4",
                "mimeType": "video/mp4",
                "parents": ["1lSSPf_kx83O0fcmSA9n4-c3dnB"],
                "webContentLink": "https://drive.google.com/uc?id=Vy5grfCTHr_12JCgxaoHrGvd&export=download",
                "createdTime": "2021-07-28T00:06:40.439Z",
                "modifiedTime": "2021-07-29T14:25:19.375Z",
                "md5Checksum": "633410252",
                "trashed": False,
            },
            {
                "id": "XuyFl10B381Co1ZE7nodTjCq",
                "name": "test_video_2.mp4",
                "mimeType": "video/mp4",
                "parents": ["TepPI157C9za"],
                "webContentLink": "https://drive.google.com/uc?id=XuyFl10B381Co1ZE7nodTjCq&export=download",
                "createdTime": "2020-08-27T12:51:41.000Z",
                "modifiedTime": "2021-07-30T12:25:19.187Z",
                "md5Checksum": "3827293107",
                "trashed": False,
            },
        ]
    },
]


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
@pytest.mark.parametrize("parent_folder", [None, "parent"])
def test_get_file_list(settings, mock_service, drive_id, parent_folder):
    """get_file_list should return expected results"""
    settings.DRIVE_SHARED_ID = drive_id
    settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID = parent_folder
    query = "(mimeType contains 'video/')"
    if parent_folder:
        query += f" and ('{parent_folder}' in parents)"

    mock_list = mock_service.return_value.files.return_value.list
    mock_execute = mock_list.return_value.execute
    mock_execute.side_effect = LIST_RESPONSES
    fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"

    drive_kwargs = {"driveId": drive_id, "corpora": "drive"} if drive_id else {}
    query_kwargs = {"q": query} if query else {}
    extra_kwargs = {**drive_kwargs, **query_kwargs}
    files = api.get_file_list(query=query, fields=fields)
    assert files == LIST_RESPONSES[0]["files"] + LIST_RESPONSES[1]["files"]
    assert mock_execute.call_count == 2
    expected_kwargs = {
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "fields": fields,
        **extra_kwargs,
    }
    mock_list.assert_any_call(**expected_kwargs)
    mock_list.assert_any_call(
        pageToken=LIST_RESPONSES[0]["nextPageToken"], **expected_kwargs
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


@pytest.mark.parametrize(
    "arg_last_dt",
    [None, datetime.strptime("2021-01-01", "%Y-%m-%d").replace(tzinfo=pytz.UTC)],
)
@pytest.mark.parametrize(
    "tracker_last_dt",
    [None, datetime.strptime("2021-02-02", "%Y-%m-%d").replace(tzinfo=pytz.UTC)],
)
@pytest.mark.parametrize("parent_folder", [None, "parent"])
@pytest.mark.parametrize("same_checksum", [True, False])
def test_import_recent_videos(
    settings, mocker, arg_last_dt, tracker_last_dt, parent_folder, same_checksum
):
    """import_recent_videos should created expected objects and call s3 tasks"""
    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID = parent_folder
    website = WebsiteFactory.create()
    DriveFileFactory.create(
        file_id=LIST_RESPONSES[1]["files"][0]["id"],
        checksum=(
            LIST_RESPONSES[1]["files"][0]["md5Checksum"]
            if same_checksum is True
            else "differentmd5"
        ),
    )

    mocker.patch(
        "gdrive_sync.api.get_parent_tree",
        side_effect=[
            [
                {
                    "id": LIST_RESPONSES[0]["files"][0]["parents"][0],
                    "name": website.short_id,
                }
            ],
            [
                {
                    "id": LIST_RESPONSES[0]["files"][1]["parents"][0],
                    "name": "no-matching-website",
                }
            ],
            [
                {
                    "id": LIST_RESPONSES[0]["files"][0]["parents"][0],
                    "name": website.short_id,
                }
            ],
            [
                {
                    "id": LIST_RESPONSES[0]["files"][1]["parents"][0],
                    "name": "no-matching-website",
                }
            ],
        ],
    )
    mock_list_files = mocker.patch(
        "gdrive_sync.api.get_file_list",
        return_value=LIST_RESPONSES[0]["files"] + LIST_RESPONSES[1]["files"],
    )
    mock_upload_task = mocker.patch(
        "gdrive_sync.api.tasks.stream_drive_file_to_s3.delay"
    )
    tracker = DriveApiQueryTrackerFactory.create(
        api_call=DRIVE_API_FILES, last_dt=tracker_last_dt
    )
    api.import_recent_videos(last_dt=arg_last_dt)

    last_dt = arg_last_dt or tracker_last_dt
    last_dt_str = last_dt.strftime("%Y-%m-%dT%H:%M:%S.%f") if last_dt else None
    dt_query = (
        f" and (modifiedTime > '{last_dt_str}' or createdTime > '{last_dt_str}')"
        if last_dt
        else ""
    )
    expected_query = f"(mimeType contains 'video/' and not trashed){dt_query}"

    if parent_folder:
        expected_query += f" and ('{parent_folder}' in parents)"

    expected_fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"
    mock_list_files.assert_called_once_with(
        query=expected_query, fields=expected_fields
    )
    for i in range(2):
        if i == 1 and same_checksum:
            with pytest.raises(AssertionError):
                mock_upload_task.assert_any_call(LIST_RESPONSES[i]["files"][0]["id"])
        else:
            mock_upload_task.assert_any_call(LIST_RESPONSES[i]["files"][0]["id"])
        assert DriveFile.objects.filter(
            file_id=LIST_RESPONSES[i]["files"][0]["id"]
        ).exists()
        assert (
            DriveFile.objects.filter(
                file_id=LIST_RESPONSES[i]["files"][1]["id"]
            ).exists()
            is False
        )
    tracker.refresh_from_db()
    assert tracker.last_dt == datetime.strptime(
        LIST_RESPONSES[1]["files"][1]["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
    ).replace(tzinfo=pytz.utc)


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
@pytest.mark.parametrize("parent_folder", [None, "parent"])
@pytest.mark.parametrize("folder_exists", [True, False])
def test_create_gdrive_folder_if_not_exists(
    settings, mocker, parent_folder, folder_exists, mock_service
):
    website_short_id = "short_id"
    website_name = "name"

    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID = parent_folder

    if folder_exists:
        existing_list_response = [{"id": "12JCgxaoHrGvd_Vy5grfCTHr"}]

    else:
        existing_list_response = []

    mock_list_files = mocker.patch(
        "gdrive_sync.api.get_file_list",
        return_value=existing_list_response,
    )

    expected_list_query = f"(mimeType = 'application/vnd.google-apps.folder') and (name = '{website_short_id}' or name = '{website_name}')"
    expected_fields = "nextPageToken, files(id, name)"

    if parent_folder:
        expected_list_query += f" and ('{parent_folder}' in parents)"

    mock_create = mock_service.return_value.files.return_value.create
    mock_execute = mock_create.return_value.execute

    api.create_gdrive_folder_if_not_exists(
        website_short_id=website_short_id, website_name=website_name
    )

    mock_list_files.assert_called_once_with(
        query=expected_list_query, fields=expected_fields
    )

    if folder_exists:
        assert mock_execute.assert_not_called
    else:
        expected_file_metadata = {
            "name": website_short_id,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_folder:
            expected_file_metadata["parents"] = [parent_folder]

        mock_create.assert_called_once_with(
            supportsAllDrives=True, body=expected_file_metadata, fields="id"
        )
