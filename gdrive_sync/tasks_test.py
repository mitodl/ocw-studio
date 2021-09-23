"""Tests for gdrive_sync tasks"""
from datetime import datetime

import pytest
import pytz

from gdrive_sync import tasks
from gdrive_sync.conftest import LIST_FILE_RESPONSES, LIST_VIDEO_RESPONSES
from gdrive_sync.constants import (
    DRIVE_API_FILES,
    DRIVE_FOLDER_FILES,
    DRIVE_FOLDER_VIDEOS,
)
from gdrive_sync.factories import DriveApiQueryTrackerFactory, DriveFileFactory
from gdrive_sync.models import DriveFile
from gdrive_sync.tasks import (
    create_resource_from_gdrive,
    import_gdrive_files,
    import_gdrive_videos,
    import_recent_files,
    import_website_files,
    transcode_drive_file_video,
)
from websites.constants import RESOURCE_TYPE_DOCUMENT
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("short_id", [None, "12.1-fall-2020"])
def test_import_gdrive_files(mocker, mocked_celery, short_id):
    """ Files should be imported only if required settings are present"""
    mocker.patch("gdrive_sync.tasks.is_gdrive_enabled", return_value=True)
    task_name = "import_website_files" if short_id else "import_recent_files"
    mock_task = mocker.patch(f"gdrive_sync.tasks.{task_name}.si")
    with pytest.raises(mocked_celery.replace_exception_class):
        import_gdrive_files.delay(short_id=short_id)
    if short_id:
        mock_task.assert_called_once_with(short_id)
    else:
        mock_task.assert_called_once_with(import_video=False)


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_stream_drive_file_to_s3(settings, mocker, shared_id, drive_creds):
    """ File should be streamed only if required settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_stream = mocker.patch("gdrive_sync.tasks.api.stream_to_s3")
    drive_file = DriveFileFactory.create()
    tasks.stream_drive_file_to_s3.delay(drive_file.file_id)
    assert mock_stream.call_count == (1 if shared_id and drive_creds else 0)


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_create_gdrive_folders(settings, mocker, shared_id, drive_creds):
    """ Folder should be created if settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_create_folder = mocker.patch("gdrive_sync.tasks.api.create_gdrive_folders")
    tasks.create_gdrive_folders.delay("test")
    assert mock_create_folder.call_count == (1 if shared_id and drive_creds else 0)


@pytest.mark.parametrize("account_id", [None, "accountid123"])
@pytest.mark.parametrize("region", [None, "us-west-1"])
@pytest.mark.parametrize("role_name", [None, "test-role"])
def test_transcode_drive_file_video(settings, mocker, account_id, region, role_name):
    """ transcode_drive_file_video should create Video object and call create_media_convert_job"""
    settings.AWS_ACCOUNT_ID = account_id
    settings.AWS_REGION = region
    settings.AWS_ROLE_NAME = role_name
    mock_convert_job = mocker.patch("gdrive_sync.tasks.create_media_convert_job")
    drive_file = DriveFileFactory.create()
    transcode_drive_file_video.delay(drive_file.file_id)
    drive_file.refresh_from_db()
    if account_id and region and role_name:
        assert drive_file.video.source_key == drive_file.s3_key
        mock_convert_job.assert_called_once_with(drive_file.video)
    else:
        assert drive_file.video is None
        mock_convert_job.assert_not_called()


# pylint:disable=too-many-arguments, too-many-locals
@pytest.mark.parametrize(
    "arg_last_dt",
    [None, datetime.strptime("2021-01-01", "%Y-%m-%d").replace(tzinfo=pytz.UTC)],
)
@pytest.mark.parametrize(
    "tracker_last_dt",
    [None, datetime.strptime("2021-02-02", "%Y-%m-%d").replace(tzinfo=pytz.UTC)],
)
@pytest.mark.parametrize(
    "parent_folder,parent_folder_in_ancestors",
    [(None, False), ("parent", True), ("parent", False)],
)
@pytest.mark.parametrize("same_checksum", [True, False])
@pytest.mark.parametrize("import_video", [True, False])
def test_import_recent_files(
    settings,
    mocker,
    mocked_celery,
    arg_last_dt,
    tracker_last_dt,
    parent_folder,
    parent_folder_in_ancestors,
    same_checksum,
    import_video,
):
    """import_recent_files should created expected objects and call s3 tasks"""
    mocker.patch("gdrive_sync.tasks.is_gdrive_enabled", return_value=True)
    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = parent_folder
    website = WebsiteFactory.create()
    DriveFileFactory.create(
        file_id=LIST_VIDEO_RESPONSES[1]["files"][0]["id"],
        name=LIST_VIDEO_RESPONSES[1]["files"][0]["name"],
        checksum=(
            LIST_VIDEO_RESPONSES[1]["files"][0]["md5Checksum"]
            if same_checksum is True
            else "differentmd5"
        ),
    )

    parent_tree_responses = [
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][0]["parents"][0],
                "name": website.short_id,
            },
            {
                "id": "abc123",
                "name": DRIVE_FOLDER_VIDEOS if import_video else DRIVE_FOLDER_FILES,
            },
        ],
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][1]["parents"][0],
                "name": "no-matching-website",
            },
            {
                "id": "xyz987",
                "name": DRIVE_FOLDER_VIDEOS if import_video else DRIVE_FOLDER_FILES,
            },
        ],
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][0]["parents"][0],
                "name": website.short_id,
            },
            {
                "id": "def456",
                "name": DRIVE_FOLDER_VIDEOS if import_video else DRIVE_FOLDER_FILES,
            },
        ],
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][1]["parents"][0],
                "name": "no-matching-website",
            },
            {
                "id": "ghi789",
                "name": DRIVE_FOLDER_VIDEOS if import_video else DRIVE_FOLDER_FILES,
            },
        ],
    ]

    if parent_folder_in_ancestors:
        for response in parent_tree_responses:
            response.append(
                {
                    "id": "parent",
                    "name": "ancestor_exists",
                }
            )

    mocker.patch("gdrive_sync.api.get_parent_tree", side_effect=parent_tree_responses)

    mock_list_files = mocker.patch(
        "gdrive_sync.tasks.get_file_list",
        return_value=LIST_VIDEO_RESPONSES[0]["files"]
        + LIST_VIDEO_RESPONSES[1]["files"],
    )
    mock_upload_task = mocker.patch("gdrive_sync.tasks.stream_drive_file_to_s3.s")
    mock_second_task = mocker.patch(
        "gdrive_sync.tasks.transcode_drive_file_video.si"
        if import_video
        else "gdrive_sync.tasks.create_resource_from_gdrive.si"
    )

    tracker = DriveApiQueryTrackerFactory.create(
        api_call=DRIVE_API_FILES, last_dt=tracker_last_dt, for_video=import_video
    )

    with pytest.raises(mocked_celery.replace_exception_class):
        import_recent_files.delay(last_dt=arg_last_dt, import_video=import_video)

    last_dt = arg_last_dt or tracker_last_dt
    last_dt_str = last_dt.strftime("%Y-%m-%dT%H:%M:%S.%f") if last_dt else None
    dt_query = (
        f" and (modifiedTime > '{last_dt_str}' or createdTime > '{last_dt_str}')"
        if last_dt
        else ""
    )
    conditional_q = "" if import_video else "not "
    expected_query = (
        f"({conditional_q}mimeType contains 'video/' and not trashed){dt_query}"
    )

    expected_fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"
    mock_list_files.assert_called_once_with(
        query=expected_query, fields=expected_fields
    )
    tracker.refresh_from_db()
    for i in range(2):
        if (i == 1 and same_checksum) or (
            parent_folder and not parent_folder_in_ancestors
        ):  # chained tasks should not be run (wrong folder, or same checksum & name)
            with pytest.raises(AssertionError):
                mock_upload_task.assert_any_call(
                    LIST_VIDEO_RESPONSES[i]["files"][0]["id"]
                )
            with pytest.raises(AssertionError):
                mock_second_task.assert_any_call(
                    LIST_VIDEO_RESPONSES[i]["files"][0]["id"]
                )
        else:  # chained tasks should be run
            mock_upload_task.assert_any_call(LIST_VIDEO_RESPONSES[i]["files"][0]["id"])
            assert (
                tracker.last_dt
                == datetime.strptime(
                    LIST_VIDEO_RESPONSES[0]["files"][0]["modifiedTime"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=pytz.utc)
            )
            mock_second_task.assert_any_call(LIST_VIDEO_RESPONSES[i]["files"][0]["id"])
        if (
            not parent_folder or parent_folder_in_ancestors
        ):  # DriveFile should be created
            assert DriveFile.objects.filter(
                file_id=LIST_VIDEO_RESPONSES[i]["files"][0]["id"]
            ).exists()
        assert (
            DriveFile.objects.filter(
                file_id=LIST_VIDEO_RESPONSES[i]["files"][1]["id"]
            ).exists()
            is False
        )


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_import_gdrive_videos(settings, mocker, mocked_celery, shared_id, drive_creds):
    """import_gdrive_videos should call import_recent_files with import_video=True"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_import_files = mocker.patch("gdrive_sync.tasks.import_recent_files.si")
    if shared_id and drive_creds:
        with pytest.raises(mocked_celery.replace_exception_class):
            import_gdrive_videos.delay()
        mock_import_files.assert_called_once_with(import_video=True)
    else:
        mock_import_files.assert_not_called()


def test_create_resource_from_gdrive(mocker):
    """create_resource_from_gdrive should create a WebsiteContent object linked to a DriveFile object"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type", return_value="application/ms-word"
    )
    drive_file = DriveFileFactory.create(s3_key="test/path/word.docx")
    create_resource_from_gdrive.delay(drive_file.file_id)
    content = WebsiteContent.objects.filter(
        website=drive_file.website,
        title=drive_file.name,
        file=drive_file.s3_key,
        type="resource",
        metadata={"filetype": RESOURCE_TYPE_DOCUMENT},
    ).first()
    assert content is not None
    drive_file.refresh_from_db()
    assert drive_file.resource == content


def test_create_resource_from_gdrive_update(mocker):
    """create_resource_from_gdrive should update a WebsiteContent object linked to a DriveFile object"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type", return_value="application/ms-word"
    )
    content = WebsiteContentFactory.create(file="test/path/old.doc")
    drive_file = DriveFileFactory.create(
        website=content.website, s3_key="test/path/word.docx", resource=content
    )
    assert content.file != drive_file.s3_key
    create_resource_from_gdrive.delay(drive_file.file_id)
    content.refresh_from_db()
    drive_file.refresh_from_db()
    assert content.file == drive_file.s3_key
    assert drive_file.resource == content


def test_import_website_files(mocker, mocked_celery):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    website = WebsiteFactory.create()
    drive_files = DriveFileFactory.create_batch(2, website=website)
    mock_process_file_result = mocker.patch(
        "gdrive_sync.tasks.process_file_result", side_effect=drive_files
    )
    mock_stream_task = mocker.patch("gdrive_sync.tasks.stream_drive_file_to_s3.s")
    mock_create_resource = mocker.patch(
        "gdrive_sync.tasks.create_resource_from_gdrive.si"
    )
    mocker.patch(
        "gdrive_sync.tasks.get_file_list",
        side_effect=[
            [
                {
                    "id": "websiteFolderId",
                    "name": website.short_id,
                },
            ],
            [
                {
                    "id": "websiteFileFinalFolderId",
                    "name": DRIVE_FOLDER_FILES,
                },
            ],
            LIST_FILE_RESPONSES[0]["files"],
        ],
    )
    with pytest.raises(mocked_celery.replace_exception_class):
        import_website_files.delay(website.short_id)
    assert mock_process_file_result.call_count == 2
    for drive_file in drive_files:
        mock_stream_task.assert_any_call(drive_file.file_id)
        mock_create_resource.assert_any_call(drive_file.file_id)


def test_import_website_files_dupe_site_folders(mocker):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    website = WebsiteFactory.create()
    mocker.patch(
        "gdrive_sync.tasks.get_file_list",
        return_value=[
            {
                "id": "websiteFolderId",
                "name": website.short_id,
            },
            {
                "id": "websiteFolderId2",
                "name": website.short_id,
            },
        ],
    )
    with pytest.raises(Exception) as exc:
        import_website_files.delay(website.short_id)
    assert exc.value.args == (
        "Expected 1 drive folder for %s but found %d",
        website.short_id,
        2,
    )


def test_import_website_files_missing_folder(mocker):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    website = WebsiteFactory.create()
    mocker.patch(
        "gdrive_sync.tasks.get_file_list",
        side_effect=[
            [
                {
                    "id": "websiteFolderId",
                    "name": website.short_id,
                },
            ],
            [],
        ],
    )
    with pytest.raises(Exception) as exc:
        import_website_files.delay(website.short_id)
    assert exc.value.args == (
        "Expected 1 drive folder for %s/files_final but found %d",
        website.short_id,
        0,
    )
