"""gdrive_sync.api tests"""
import json
import os

import pytest
from botocore.exceptions import ClientError
from moto import mock_s3
from requests import HTTPError

from gdrive_sync import api
from gdrive_sync.api import (
    create_gdrive_resource_content,
    get_resource_type,
    process_file_result,
    transcode_gdrive_video,
    walk_gdrive_folder,
)
from gdrive_sync.conftest import LIST_VIDEO_RESPONSES
from gdrive_sync.constants import (
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    DriveFileStatus,
)
from gdrive_sync.factories import DriveFileFactory
from gdrive_sync.models import DriveFile
from main.s3_utils import get_s3_resource
from videos.constants import VideoStatus
from websites.constants import (
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_OTHER,
    RESOURCE_TYPE_VIDEO,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


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
def test_query_files(settings, mock_service, drive_id):
    """query_files should return expected results"""
    settings.DRIVE_SHARED_ID = drive_id
    query = "(mimeType contains 'video/')"

    mock_list = mock_service.return_value.files.return_value.list
    mock_execute = mock_list.return_value.execute
    mock_execute.side_effect = LIST_VIDEO_RESPONSES

    drive_kwargs = {"driveId": drive_id, "corpora": "drive"} if drive_id else {}
    query_kwargs = {"q": query} if query else {}
    extra_kwargs = {**drive_kwargs, **query_kwargs}
    files = api.query_files(query=query, fields=DRIVE_FILE_FIELDS)
    assert (
        list(files)
        == LIST_VIDEO_RESPONSES[0]["files"] + LIST_VIDEO_RESPONSES[1]["files"]
    )
    assert mock_execute.call_count == 2
    expected_kwargs = {
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "fields": DRIVE_FILE_FIELDS,
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


@pytest.mark.parametrize("is_video", [True, False])
def test_stream_to_s3(settings, mocker, is_video):
    """stream_to_s3 should make expected drive api and S3 upload calls"""
    mock_service = mocker.patch("gdrive_sync.api.get_drive_service")
    mock_download = mocker.patch("gdrive_sync.api.streaming_download")
    mock_boto3 = mocker.patch("gdrive_sync.api.boto3")
    mock_bucket = mock_boto3.resource.return_value.Bucket.return_value
    drive_file = DriveFileFactory.create()
    prefix = None if is_video else "courses"
    api.stream_to_s3(drive_file, prefix=prefix)
    mock_service.return_value.permissions.return_value.create.assert_called_once()
    if is_video:
        key = f"{settings.DRIVE_S3_UPLOAD_PREFIX}/{drive_file.website.short_id}/{drive_file.file_id}/{drive_file.name}"
    else:
        key = f"courses/{drive_file.website.short_id}/{drive_file.name}"
    mock_bucket.upload_fileobj.assert_called_with(
        Fileobj=mocker.ANY,
        Key=key,
        ExtraArgs={"ContentType": drive_file.mime_type, "ACL": "public-read"},
    )
    mock_download.assert_called_once_with(drive_file)
    mock_service.return_value.permissions.return_value.delete.assert_called_once()
    drive_file.refresh_from_db()
    assert drive_file.status == DriveFileStatus.UPLOAD_COMPLETE
    assert drive_file.s3_key == key


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
        "gdrive_sync.api.query_files", side_effect=[existing_list_response, [], [], []]
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
    mock_execute.side_effect = [
        {"id": site_folder_id},
        {"id": "sub1"},
        {"id": "sub2"},
        {"id": "sub3"},
    ]

    api.create_gdrive_folders(website_short_id=website_short_id)

    mock_list_files.assert_any_call(query=expected_folder_query, fields=expected_fields)

    if folder_exists and parent_folder:
        mock_get_parent_tree.assert_called_once_with(["first_parent"])
    else:
        mock_get_parent_tree.assert_not_called()

    if not folder_exists or (parent_folder and not parent_folder_in_ancestors):
        expected_file_metadata = {
            "name": website_short_id,
            "mimeType": DRIVE_MIMETYPE_FOLDER,
        }

        if parent_folder:
            expected_file_metadata["parents"] = [parent_folder]
        else:
            expected_file_metadata["parents"] = ["test_drive"]

        mock_create.assert_any_call(
            supportsAllDrives=True, body=expected_file_metadata, fields="id"
        )

    for subfolder in [DRIVE_FOLDER_FILES_FINAL, DRIVE_FOLDER_VIDEOS_FINAL]:
        expected_folder_query = (
            f"{base_query}name = '{subfolder}' and parents = '{site_folder_id}'"
        )
        expected_file_metadata = {
            "name": subfolder,
            "mimeType": DRIVE_MIMETYPE_FOLDER,
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


@pytest.mark.parametrize("is_video", [True, False])
@pytest.mark.parametrize("in_video_folder", [True, False])
@pytest.mark.parametrize("checksum", ["633410252", None])
@pytest.mark.parametrize("link", ["http://download/url", None])
def test_process_file_result(
    settings, mocker, is_video, in_video_folder, checksum, link
):
    """process_file_result should create a DriveFile only if all conditions are met"""
    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = "parent"
    website = WebsiteFactory.create()

    mocker.patch(
        "gdrive_sync.api.get_parent_tree",
        return_value=[
            {
                "id": "parent",
                "name": "ancestor_exists",
            },
            {
                "id": "websiteId",
                "name": website.short_id,
            },
            {
                "id": "subFolderId",
                "name": DRIVE_FOLDER_VIDEOS_FINAL
                if in_video_folder
                else DRIVE_FOLDER_FILES_FINAL,
            },
        ],
    )

    file_result = {
        "id": "Ay5grfCTHr_12JCgxaoHrGve",
        "name": "test_file",
        "mimeType": "video/mp4" if is_video else "image/jpeg",
        "parents": ["subFolderId"],
        "webContentLink": link,
        "createdTime": "2021-07-28T00:06:40.439Z",
        "modifiedTime": "2021-07-29T14:25:19.375Z",
        "md5Checksum": checksum,
        "trashed": False,
    }
    process_file_result(file_result)
    drive_file = DriveFile.objects.filter(file_id=file_result["id"]).first()
    file_exists = drive_file is not None
    assert file_exists is (
        link is not None
        and ((is_video and in_video_folder) or (not is_video and not in_video_folder))
    )
    if drive_file:
        assert drive_file.checksum == checksum


def test_process_file_result_exception(settings, mocker):
    """Verify that an exception is logged if anything goes wrong"""
    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = "parent"
    mocker.patch("gdrive_sync.api.get_parent_tree", side_effect=Exception)
    mock_log = mocker.patch("gdrive_sync.api.log.exception")
    file_result = {
        "id": "Ay5grfCTHr_12JCgxaoHrGve",
        "parents": ["subFolderId"],
        "trashed": False,
    }
    process_file_result(file_result)
    mock_log.assert_called_once_with(
        "Error processing gdrive file id %s", file_result["id"]
    )


def test_walk_gdrive_folder(mocker):
    """walk_gdrive_folder should yield all expected files"""
    files = [
        [
            {"id": "image1.jpg", "mimeType": "image/jpeg"},
            {"id": "image2.jpg", "mimeType": "image/jpeg"},
            {"id": "subfolder1", "mimeType": DRIVE_MIMETYPE_FOLDER},
            {"id": "subfolder2", "mimeType": DRIVE_MIMETYPE_FOLDER},
        ],
        [
            {"id": "subfolder1a.jpg", "mimeType": "image/jpeg"},
            {"id": "subfolder1b.jpg", "mimeType": "image/jpeg"},
            {"id": "subfolder1_1", "mimeType": DRIVE_MIMETYPE_FOLDER},
        ],
        [
            {"id": "subfolder1_1a.pdf", "mimeType": "application/pdf"},
            {"id": "subfolder1_1b.pdf", "mimeType": "application/pdf"},
        ],
        [
            {"id": "subfolder2a.mp4", "mimeType": "application/pdf"},
            {"id": "subfolder2b.mp4", "mimeType": "application/pdf"},
        ],
    ]
    mock_query_files = mocker.patch("gdrive_sync.api.query_files", side_effect=files)
    assert (list(walk_gdrive_folder("folderId", "field1,field2,field3"))) == [
        item
        for sublist in files
        for item in sublist
        if item["mimeType"] != DRIVE_MIMETYPE_FOLDER
    ]
    assert (
        mock_query_files.call_count == 4
    )  # parent, subfolder1, subfolder1_1, subfolder2


@pytest.mark.parametrize(
    "mime_type", ["application/pdf", "application/vnd.ms-powerpoint"]
)
def test_create_gdrive_resource_content(mocker, mime_type):
    """create_resource_from_gdrive should create a WebsiteContent object linked to a DriveFile object"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type", return_value="application/ms-word"
    )
    drive_file = DriveFileFactory.create(
        s3_key="test/path/word.docx", mime_type=mime_type
    )
    create_gdrive_resource_content(drive_file)
    content = WebsiteContent.objects.filter(
        website=drive_file.website,
        title=drive_file.name,
        file=drive_file.s3_key,
        type="resource",
        is_page_content=True,
        metadata={"resourcetype": RESOURCE_TYPE_DOCUMENT, "file_type": mime_type},
    ).first()
    assert content is not None
    assert content.dirpath == "content/resource"
    assert content.filename == os.path.splitext(drive_file.name)[0]
    drive_file.refresh_from_db()
    assert drive_file.resource == content


def test_create_gdrive_resource_content_update(mocker):
    """create_resource_from_gdrive should update a WebsiteContent object linked to a DriveFile object"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type", return_value="application/ms-word"
    )
    content = WebsiteContentFactory.create(file="test/path/old.doc")
    drive_file = DriveFileFactory.create(
        website=content.website, s3_key="test/path/word.docx", resource=content
    )
    assert content.file != drive_file.s3_key
    create_gdrive_resource_content(drive_file)
    content.refresh_from_db()
    drive_file.refresh_from_db()
    assert content.file == drive_file.s3_key
    assert drive_file.resource == content


@pytest.mark.parametrize("account_id", [None, "accountid123"])
@pytest.mark.parametrize("region", [None, "us-west-1"])
@pytest.mark.parametrize("role_name", [None, "test-role"])
def test_transcode_gdrive_video(settings, mocker, account_id, region, role_name):
    """ transcode_gdrive_video should create Video object and call create_media_convert_job"""
    settings.AWS_ACCOUNT_ID = account_id
    settings.AWS_REGION = region
    settings.AWS_ROLE_NAME = role_name
    mock_convert_job = mocker.patch("gdrive_sync.api.create_media_convert_job")
    drive_file = DriveFileFactory.create()
    transcode_gdrive_video(drive_file)
    drive_file.refresh_from_db()
    if account_id and region and role_name:
        assert drive_file.video.source_key == drive_file.s3_key
        mock_convert_job.assert_called_once_with(drive_file.video)
    else:
        assert drive_file.video is None
        mock_convert_job.assert_not_called()


def test_transcode_gdrive_video_error(settings, mocker):
    """Video status should be set to failure if a client error occurs"""
    settings.AWS_ACCOUNT_ID = "accountABC"
    settings.AWS_REGION = "us-east-1"
    settings.AWS_ROLE_NAME = "roleDEF"
    mocker.patch(
        "gdrive_sync.api.create_media_convert_job",
        side_effect=ClientError({"Error": {}}, "transcode"),
    )
    mock_log = mocker.patch("gdrive_sync.api.log.exception")
    drive_file = DriveFileFactory.create()
    transcode_gdrive_video(drive_file)
    drive_file.refresh_from_db()
    mock_log.assert_called_once_with(
        "Error creating transcode job for %s", drive_file.video.source_key
    )
    assert drive_file.video.status == VideoStatus.FAILED
