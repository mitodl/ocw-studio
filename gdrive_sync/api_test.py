"""gdrive_sync.api tests"""
import json
from datetime import timedelta

import pytest
from botocore.exceptions import ClientError
from googleapiclient.http import MediaDownloadProgress
from mitol.common.utils import now_in_utc
from moto import mock_s3
from requests import HTTPError

from gdrive_sync import api
from gdrive_sync.api import (
    GDriveStreamReader,
    create_gdrive_resource_content,
    gdrive_root_url,
    get_resource_type,
    process_file_result,
    rename_file,
    transcode_gdrive_video,
    update_sync_status,
    walk_gdrive_folder,
)
from gdrive_sync.conftest import LIST_VIDEO_RESPONSES
from gdrive_sync.constants import (
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    DriveFileStatus,
    WebsiteSyncStatus,
)
from gdrive_sync.factories import DriveFileFactory
from gdrive_sync.models import DriveFile
from main.s3_utils import get_boto3_resource
from videos.constants import VideoJobStatus, VideoStatus
from videos.factories import VideoFactory, VideoJobFactory
from websites.constants import (
    CONTENT_FILENAMES_FORBIDDEN,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_OTHER,
    RESOURCE_TYPE_VIDEO,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name, too-many-arguments, unused-argument, protected-access


@pytest.fixture
def mock_service(mocker):
    """Mock google drive service"""
    return mocker.patch("gdrive_sync.api.get_drive_service")


@pytest.fixture
def mock_get_s3_content_type(mocker):
    """Mock gdrive_sync.api.get_s3_content_type"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type", return_value="application/ms-word"
    )


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
@pytest.mark.parametrize("current_s3_key", [None, "courses/website/current-file.png"])
def test_stream_to_s3(settings, mocker, is_video, current_s3_key):
    """stream_to_s3 should make expected drive api and S3 upload calls"""
    settings.ENVIRONMENT = "test"
    mock_download = mocker.patch("gdrive_sync.api.GDriveStreamReader")
    mock_boto3 = mocker.patch("main.s3_utils.boto3")
    mock_bucket = mock_boto3.resource.return_value.Bucket.return_value
    drive_file = DriveFileFactory.create(
        name="A (Test) File!.ext",
        s3_key=current_s3_key,
        mime_type="video/mp4" if is_video else "application/pdf",
        drive_path=f"website/{DRIVE_FOLDER_VIDEOS_FINAL if is_video else DRIVE_FOLDER_FILES_FINAL}",
    )
    api.stream_to_s3(drive_file)
    if current_s3_key:
        expected_key = current_s3_key
    elif is_video:
        expected_key = f"{settings.DRIVE_S3_UPLOAD_PREFIX}/{drive_file.website.name}/{drive_file.file_id}/a-test-file.ext"
    else:
        expected_key = (
            f"{drive_file.s3_prefix}/{drive_file.website.name}/a-test-file.ext"
        )

    if is_video:
        expected_extra_args = {
            "ContentType": drive_file.mime_type,
            "ACL": "public-read",
            "ContentDisposition": "attachment",
        }
    else:
        expected_extra_args = {
            "ContentType": drive_file.mime_type,
            "ACL": "public-read",
        }

    mock_bucket.upload_fileobj.assert_called_with(
        Fileobj=mocker.ANY,
        Key=expected_key,
        ExtraArgs=expected_extra_args,
    )
    mock_download.assert_called_once_with(drive_file)
    drive_file.refresh_from_db()
    assert drive_file.status == DriveFileStatus.UPLOAD_COMPLETE
    assert drive_file.s3_key == expected_key


@pytest.mark.django_db
@pytest.mark.parametrize("num_errors", [2, 3, 4])
def test_stream_to_s3_error(settings, mocker, num_errors):
    """Task should mark DriveFile status as failed if an s3 upload error occurs more often than retries"""
    settings.ENVIRONMENT = "test"
    settings.CONTENT_SYNC_RETRIES = 3
    should_raise = num_errors >= 3
    mocker.patch("gdrive_sync.api.GDriveStreamReader")
    mock_boto3 = mocker.patch("main.s3_utils.boto3")
    mock_boto3.resource.return_value.Bucket.side_effect = [
        *[HTTPError() for _ in range(num_errors)],
        mocker.Mock(),
    ]
    drive_file = DriveFileFactory.create()
    if should_raise:
        with pytest.raises(HTTPError):
            api.stream_to_s3(drive_file)
    else:
        api.stream_to_s3(drive_file)
    drive_file.refresh_from_db()
    assert drive_file.status == (
        DriveFileStatus.UPLOAD_FAILED
        if should_raise
        else DriveFileStatus.UPLOAD_COMPLETE
    )


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

    empty_yield = iter([])
    if folder_exists:
        existing_list_response = [{"id": site_folder_id, "parents": ["first_parent"]}]
    else:
        existing_list_response = []

    mock_list_files = mocker.patch(
        "gdrive_sync.api.query_files",
        side_effect=[
            iter(existing_list_response),
            empty_yield,
            empty_yield,
            empty_yield,
        ],
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
    "filename, in_file_dir, mimetype, expected_type",
    [
        ["file.docx", True, "application/ms-word", RESOURCE_TYPE_DOCUMENT],
        ["file.html", True, "text/html", RESOURCE_TYPE_DOCUMENT],
        ["file.mp4", True, "video/mp4", RESOURCE_TYPE_OTHER],
        ["file.mp4", False, "video/mp4", RESOURCE_TYPE_VIDEO],
        ["file.jpeg", True, "image/jpeg", RESOURCE_TYPE_IMAGE],
        ["file.py", True, "application/python", RESOURCE_TYPE_OTHER],
    ],
)
def test_get_resource_type(
    settings, in_file_dir, filename, mimetype, expected_type
) -> str:
    """get_resource_type should return the expected value for an S3 object"""
    settings.ENVIRONMENT = "test"
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"
    settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
    conn = get_boto3_resource("s3")
    conn.create_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
    test_bucket = conn.Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)
    test_bucket.objects.all().delete()
    test_bucket.put_object(Key=filename, Body=b"", ContentType=mimetype)
    drive_file = DriveFileFactory.build(
        s3_key=filename,
        drive_path=(
            DRIVE_FOLDER_FILES_FINAL if in_file_dir else DRIVE_FOLDER_VIDEOS_FINAL
        ),
    )
    assert get_resource_type(drive_file) == expected_type


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
    correct_folder = is_video or (not is_video and not in_video_folder)
    process_file_result(file_result)
    drive_file = DriveFile.objects.filter(file_id=file_result["id"]).first()
    file_exists = drive_file is not None
    assert file_exists is (correct_folder and link is not None and checksum is not None)
    if drive_file:
        assert drive_file.checksum == checksum


@pytest.mark.parametrize("status", [DriveFileStatus.UPLOADING, DriveFileStatus.FAILED])
@pytest.mark.parametrize("same_checksum", [True, False])
@pytest.mark.parametrize("same_name", [True, False])
def test_process_file_result_update(settings, mocker, status, same_checksum, same_name):
    """
    An existing drive file should not be processed again if the checksum and name are the same, ond the status
    indicates that processing is complete or in progress.
    """
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
                "name": DRIVE_FOLDER_FILES_FINAL,
            },
        ],
    )
    drive_file = DriveFileFactory.create(status=status, website=website)
    file_result = {
        "id": drive_file.file_id,
        "name": drive_file.name if same_name else "new-name",
        "mimeType": "image/jpeg",
        "parents": ["subFolderId"],
        "webContentLink": "http://link",
        "createdTime": "2021-07-28T00:06:40.439Z",
        "modifiedTime": "2021-07-29T14:25:19.375Z",
        "md5Checksum": drive_file.checksum if same_checksum else "new-check-sum",
        "trashed": False,
    }
    result = process_file_result(file_result)
    assert (result is None) is (
        same_name
        and same_checksum
        and status
        in (
            DriveFileStatus.UPLOADING,
            DriveFileStatus.UPLOAD_COMPLETE,
            DriveFileStatus.TRANSCODING,
            DriveFileStatus.COMPLETE,
        )
    )


@pytest.mark.parametrize("replace_file", [True, False])
def test_process_file_result_replace_file(settings, mocker, replace_file):
    """
    If replace_file is True, the file on the same path should be replaced with the new file.
    Otherwise, a new file should be created.
    """
    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = "parent"
    mocker.patch("main.s3_utils.boto3")
    website = WebsiteFactory.create()
    parent_tree = [
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
            "name": DRIVE_FOLDER_FILES_FINAL,
        },
    ]
    mocker.patch(
        "gdrive_sync.api.get_parent_tree",
        return_value=parent_tree,
    )
    drive_file = DriveFileFactory.create(
        file_id="old_file_id",
        website=website,
        drive_path="/".join([section["name"] for section in parent_tree]),
    )
    file_result = {
        "id": "y5grfCTHr_12JCgxaoHrGve",
        "name": drive_file.name,
        "mimeType": "image/jpeg",
        "parents": ["subFolderId"],
        "webContentLink": "http://link",
        "createdTime": "2021-07-28T00:06:40.439Z",
        "modifiedTime": "2021-07-29T14:25:19.375Z",
        "md5Checksum": "check-sum-",
        "trashed": False,
    }
    process_file_result(file_result, replace_file=replace_file)
    count = DriveFile.objects.filter(name=drive_file.name).count()
    assert count == (1 if replace_file else 2)
    if replace_file:
        assert DriveFile.objects.filter(pk=drive_file.file_id).first() is None


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
    mock_query_files = mocker.patch(
        "gdrive_sync.api.query_files", side_effect=iter(files)
    )
    assert (list(walk_gdrive_folder("folderId", "field1,field2,field3"))) == [
        item
        for sublist in files
        for item in sublist
        if item["mimeType"] != DRIVE_MIMETYPE_FOLDER
    ]
    assert (
        mock_query_files.call_count == 4
    )  # parent, subfolder1, subfolder1_1, subfolder2


@pytest.fixture
def mock_gdrive_pdf(mocker):
    """Mock reading the metadata of a PDF file with blank metadata"""
    mocker.patch(
        "gdrive_sync.api.GDriveStreamReader",
        return_value=mocker.Mock(read=mocker.Mock(return_value=b"fake_bytes")),
    )
    mocker.patch(
        "gdrive_sync.api.PyPDF2.PdfReader",
        return_value=mocker.Mock(metadata={}),
    )


@pytest.mark.parametrize(
    "mime_type", ["application/pdf", "application/vnd.ms-powerpoint"]
)
def test_create_gdrive_resource_content(mime_type, mock_get_s3_content_type):
    """create_resource_from_gdrive should create a WebsiteContent object linked to a DriveFile object"""
    filenames = ["word.docx", "word!.docx", "(word?).docx"]
    deduped_names = ["word", "word2", "word3"]
    website = WebsiteFactory.create()
    for filename, deduped_name in zip(filenames, deduped_names):
        drive_file = DriveFileFactory.create(
            website=website,
            name=filename,
            s3_key=f"test/path/{deduped_name}.docx",
            mime_type=mime_type,
        )
        create_gdrive_resource_content(drive_file)
        content = WebsiteContent.objects.filter(
            website=website,
            title=filename,
            type="resource",
            is_page_content=True,
        ).first()
        assert content is not None
        assert content.dirpath == "content/resource"
        assert content.filename == deduped_name
        assert content.metadata["resourcetype"] == RESOURCE_TYPE_DOCUMENT
        assert content.metadata["file_type"] == mime_type
        assert content.metadata["image"] == ""
        assert content.metadata["license"] == "default_license_specificed_in_config"
        drive_file.refresh_from_db()
        assert drive_file.resource == content


def test_create_gdrive_resource_content_forbidden_name(
    mock_get_s3_content_type, mock_gdrive_pdf
):
    """content for a google drive file with a forbidden name should have its filename attribute modified"""
    drive_file = DriveFileFactory.create(
        name=f"{CONTENT_FILENAMES_FORBIDDEN[0]}.pdf",
        s3_key=f"test/path/{CONTENT_FILENAMES_FORBIDDEN[0]}.pdf",
        mime_type="application/pdf",
    )
    create_gdrive_resource_content(drive_file)
    drive_file.refresh_from_db()
    assert (
        drive_file.resource.filename
        == f"{CONTENT_FILENAMES_FORBIDDEN[0]}-{CONTENT_TYPE_RESOURCE}"
    )


def test_gdrive_pdf_failure(mock_get_s3_content_type, mocker):
    """Non-valid PDFs should raise an error"""
    mocker.patch(
        "gdrive_sync.api.GDriveStreamReader",
        return_value=mocker.Mock(read=mocker.Mock(return_value=b"fake_bytes")),
    )
    mock_log = mocker.patch("gdrive_sync.api.log.exception")
    drive_file = DriveFileFactory.create(
        name="mylecturenotes123.pdf",
        s3_key="test/path/mylecturenotes123.pdf",
        mime_type="application/pdf",
    )
    create_gdrive_resource_content(drive_file)
    drive_file.refresh_from_db()
    assert drive_file.status == DriveFileStatus.FAILED
    mock_log.assert_called_once_with(
        "Could not create a resource from Google Drive file %s because it is not a valid PDF",
        drive_file.file_id,
    )


@pytest.mark.parametrize("mytitle", ["", "MyTitle"])
def test_create_gdrive_pdf(mock_get_s3_content_type, mocker, mytitle):
    """PDFs that have a non-blank title in the metadata should use that title in the resource"""
    mocker.patch(
        "gdrive_sync.api.GDriveStreamReader",
        return_value=mocker.Mock(read=mocker.Mock(return_value=b"fake_bytes")),
    )
    mocker.patch(
        "gdrive_sync.api.PyPDF2.PdfReader",
        return_value=mocker.Mock(metadata={"/Title": mytitle}),
    )
    drive_file = DriveFileFactory.create(
        name="mylecturenotes123.pdf",
        s3_key="test/path/mylecturenotes123.pdf",
        mime_type="application/pdf",
    )
    create_gdrive_resource_content(drive_file)
    drive_file.refresh_from_db()
    assert drive_file.resource.title == mytitle if mytitle != "" else drive_file.name


def test_create_gdrive_resource_content_update(mock_get_s3_content_type):
    """create_resource_from_gdrive should update a WebsiteContent object linked to a DriveFile object"""
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


def test_create_gdrive_resource_content_error(mocker):
    """create_resource_from_gdrive should log an exception, update status if something goes wrong"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type",
        return_value=Exception("Could not determine resource type"),
    )
    mock_log = mocker.patch("gdrive_sync.api.log.exception")
    content = WebsiteContentFactory.create()
    drive_file = DriveFileFactory.create(
        website=content.website, s3_key="test/path/word.docx", resource=content
    )
    create_gdrive_resource_content(drive_file)
    content.refresh_from_db()
    drive_file.refresh_from_db()
    assert drive_file.status == DriveFileStatus.FAILED
    mock_log.assert_called_once_with(
        "Error creating resource for drive file %s", drive_file.file_id
    )


@pytest.mark.parametrize("account_id", [None, "accountid123"])
@pytest.mark.parametrize("region", [None, "us-west-1"])
@pytest.mark.parametrize("role_name", [None, "test-role"])
def test_transcode_gdrive_video(settings, mocker, account_id, region, role_name):
    """transcode_gdrive_video should create Video object and call create_media_convert_job"""
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


@pytest.mark.parametrize(
    "prior_status",
    [VideoJobStatus.CREATED, VideoJobStatus.CREATED, VideoJobStatus.FAILED],
)
def test_transcode_gdrive_video_prior_job(settings, mocker, prior_status):
    """create_media_convert_job should be called only if the prior job failed"""
    settings.AWS_ACCOUNT_ID = "accountABC"
    settings.AWS_REGION = "us-east-1"
    settings.AWS_ROLE_NAME = "roleDEF"
    mock_convert_job = mocker.patch("gdrive_sync.api.create_media_convert_job")
    video = VideoFactory.create()
    drive_file = DriveFileFactory.create(
        website=video.website, video=video, s3_key=video.source_key
    )
    VideoJobFactory.create(video=video, status=prior_status)
    transcode_gdrive_video(drive_file)
    drive_file.refresh_from_db()
    if prior_status != VideoJobStatus.CREATED:
        mock_convert_job.assert_called_once_with(drive_file.video)
    else:
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
    with pytest.raises(ClientError):
        transcode_gdrive_video(drive_file)
    drive_file.refresh_from_db()
    mock_log.assert_called_once_with(
        "Error creating transcode job for %s", drive_file.video.source_key
    )
    assert drive_file.video.status == VideoStatus.FAILED


@pytest.mark.parametrize(
    "shared_id, parent_id, folder",
    [
        [None, "def456", None],
        ["", "def456", None],
        ["abc123", None, "abc123"],
        ["abc123", "", "abc123"],
        ["abc123", "def456", "def456"],
    ],
)
def test_gdrive_root_url(settings, shared_id, parent_id, folder):
    """gdrive_root_url should return the expected URL"""
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = {"creds": True}
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = parent_id
    settings.DRIVE_SHARED_ID = shared_id
    assert gdrive_root_url() == (
        f"https://drive.google.com/drive/folders/{folder}/" if folder else None
    )


@pytest.mark.parametrize(
    "file_errors, site_errors, status",
    [
        [[None, None], None, WebsiteSyncStatus.COMPLETE],
        [[None, None], ["Error querying files_final folder"], WebsiteSyncStatus.ERRORS],
        [[], [], WebsiteSyncStatus.COMPLETE],
        [[], ["Error querying Google Drive"], WebsiteSyncStatus.FAILED],
        [["Could not sync to S3", None], [], WebsiteSyncStatus.ERRORS],
        [
            ["Could not sync to S3", None],
            ["Could not query videos_final"],
            WebsiteSyncStatus.ERRORS,
        ],
        [
            ["Could not sync to S3", "Could not create resource"],
            [],
            WebsiteSyncStatus.FAILED,
        ],
    ],
)
def test_update_sync_status(file_errors, site_errors, status):
    """update_sync_status should update the website sync_status field as expected"""
    now = now_in_utc()
    website = WebsiteFactory.create(
        synced_on=now, sync_status=WebsiteSyncStatus.PROCESSING, sync_errors=site_errors
    )
    for error in file_errors:
        DriveFileFactory.create(
            website=website,
            sync_error=error,
            sync_dt=now,
            resource=(
                WebsiteContentFactory.create(
                    type=CONTENT_TYPE_RESOURCE, website=website
                )
                if not error
                else None
            ),
            status=(
                DriveFileStatus.COMPLETE if error is None else DriveFileStatus.FAILED
            ),
        )
    DriveFileFactory.create(
        website=website,
        sync_dt=now_in_utc() + timedelta(seconds=10),
        resource=WebsiteContentFactory.create(
            type=CONTENT_TYPE_RESOURCE, website=website
        ),
    )
    update_sync_status(website, now)
    website.refresh_from_db()
    assert website.sync_status == status
    assert sorted(website.sync_errors) == sorted(
        [error for error in file_errors if error] + (site_errors or [])
    )


@pytest.mark.parametrize("chunk_size", [1, 2, 3])
def test_gdrive_stream_reader(mocker, mock_service, chunk_size):
    """The GDriveStreamReader should return the expected bytes"""
    expected_bytes = [b"a", b"b", b"c"]
    bytes_idx = 0

    mock_resp = mocker.Mock(status=200)
    mocker.patch(
        "googleapiclient.http._retry_request", return_value=(mock_resp, b"abc")
    )
    reader = GDriveStreamReader(DriveFileFactory.build())

    def mock_next_chunk():
        """Overwrite the MediaIoBaseDownload.next_chunk function for testing purposes"""
        reader.downloader._fd.write(
            b"".join(expected_bytes[bytes_idx : bytes_idx + chunk_size])
        )
        return MediaDownloadProgress(bytes_idx + chunk_size, 3), bytes_idx >= 2

    reader.downloader.next_chunk = mock_next_chunk

    for i in range(0, 3, chunk_size):
        bytes_read = reader.read(amount=chunk_size)
        bytes_idx += chunk_size
        assert reader.downloader._chunksize == chunk_size
        assert bytes_read == b"".join(expected_bytes[i : i + chunk_size])


def test_rename_file(mocker, settings):
    """rename_file should update the WebsiteContent and DriveFile objects with a new file path"""
    content = WebsiteContentFactory.create(
        file="test/path/old_name.pdf", text_id="abc-123"
    )
    drive_file = DriveFileFactory.create(
        website=content.website, s3_key="test/path/old_name.pdf", resource=content
    )
    mocker.patch("main.s3_utils.boto3")
    settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
    rename_file("abc-123", "new_name.pdf")
    content.refresh_from_db()
    drive_file.refresh_from_db()
    assert content.file == "test/path/new_name.pdf"
    assert drive_file.s3_key == "test/path/new_name.pdf"


@pytest.mark.parametrize("deleted_drive_files_count", [0, 5, 10])
def test_find_missing_files(deleted_drive_files_count):
    """find_missing_files should return files that are missing from files param."""
    website = WebsiteFactory.create()
    drive_files = DriveFileFactory.create_batch(10, website=website)
    deleted_drive_files = drive_files[:deleted_drive_files_count]
    existing_drive_files = drive_files[deleted_drive_files_count:]
    files = [{"id": file.file_id} for file in existing_drive_files]

    missing_files_result = api.find_missing_files(files, website)

    deleted_file_ids = [file.file_id for file in deleted_drive_files]
    missing_files_result_ids = [file.file_id for file in missing_files_result]
    assert len(deleted_drive_files) == len(missing_files_result)
    assert all([file_id in deleted_file_ids for file_id in missing_files_result_ids])


@pytest.mark.parametrize("with_resource", [False, True])
@pytest.mark.parametrize("is_used_in_content", [False, True])
def test_delete_drive_file(mocker, with_resource, is_used_in_content):
    """delete_drive_file should delete the file and resource only if resource is not being used"""
    mocker.patch("main.s3_utils.boto3")
    website = WebsiteFactory.create()
    drive_file = DriveFileFactory.create(website=website)

    if with_resource:
        resource = WebsiteContentFactory.create(
            text_id="7d3df94e-e8dd-40bc-97f2-18e793d5ce25",
            type=CONTENT_TYPE_RESOURCE,
            website=website,
        )
        drive_file.resource = resource
        drive_file.save()

        if is_used_in_content:
            content = WebsiteContentFactory.create(
                type=CONTENT_TYPE_PAGE,
                markdown=f'{{{{% resource_link "{resource.text_id}" "{resource.filename}" %}}}}',
                website=website,
            )

    api.delete_drive_file(drive_file)

    drive_file_exists = DriveFile.objects.filter(file_id=drive_file.file_id).exists()
    if with_resource:
        resource_exists = WebsiteContent.objects.filter(pk=resource.id).exists()

    if with_resource and is_used_in_content:
        assert WebsiteContent.objects.filter(pk=content.id).exists()
        assert resource_exists
        assert drive_file_exists
    elif with_resource:
        assert not drive_file_exists
        assert not resource_exists
    else:
        assert not drive_file_exists
