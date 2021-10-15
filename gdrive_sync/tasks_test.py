"""Tests for gdrive_sync tasks"""
from datetime import datetime

import pytest
import pytz

from gdrive_sync import tasks
from gdrive_sync.conftest import LIST_FILE_RESPONSES, LIST_VIDEO_RESPONSES
from gdrive_sync.constants import (
    DRIVE_API_FILES,
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
)
from gdrive_sync.factories import DriveApiQueryTrackerFactory, DriveFileFactory
from gdrive_sync.models import DriveFile
from gdrive_sync.tasks import (
    create_resource_from_gdrive,
    import_recent_files,
    import_website_files,
    transcode_drive_file_video,
)
from websites.factories import WebsiteFactory


pytestmark = pytest.mark.django_db


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


def test_transcode_drive_file_video(mocker):
    """ transcode_drive_file_video should create Video object and call create_media_convert_job"""
    mock_transcode_call = mocker.patch("gdrive_sync.tasks.transcode_gdrive_video")
    drive_file = DriveFileFactory.create()
    transcode_drive_file_video.delay(drive_file.file_id)
    mock_transcode_call.assert_called_once_with(drive_file)


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
def test_import_recent_files_videos(
    settings,
    mocker,
    mocked_celery,
    arg_last_dt,
    tracker_last_dt,
    parent_folder,
    parent_folder_in_ancestors,
    same_checksum,
):
    """import_recent_files should created expected video objects and call s3 tasks"""
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
            {"id": "abc123", "name": DRIVE_FOLDER_VIDEOS_FINAL},
        ],
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][1]["parents"][0],
                "name": "no-matching-website",
            },
            {"id": "xyz987", "name": DRIVE_FOLDER_VIDEOS_FINAL},
        ],
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][0]["parents"][0],
                "name": website.short_id,
            },
            {"id": "def456", "name": DRIVE_FOLDER_VIDEOS_FINAL},
        ],
        [
            {
                "id": LIST_VIDEO_RESPONSES[0]["files"][1]["parents"][0],
                "name": "no-matching-website",
            },
            {"id": "ghi789", "name": DRIVE_FOLDER_VIDEOS_FINAL},
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
        "gdrive_sync.tasks.query_files",
        return_value=LIST_VIDEO_RESPONSES[0]["files"]
        + LIST_VIDEO_RESPONSES[1]["files"],
    )
    mock_upload_task = mocker.patch("gdrive_sync.tasks.stream_drive_file_to_s3.s")
    mock_transcode_task = mocker.patch(
        "gdrive_sync.tasks.transcode_drive_file_video.si"
    )
    mock_sync_content_task = mocker.patch("gdrive_sync.tasks.sync_website_content.si")

    tracker = DriveApiQueryTrackerFactory.create(
        api_call=DRIVE_API_FILES, last_dt=tracker_last_dt
    )

    if parent_folder_in_ancestors or parent_folder is None:
        with pytest.raises(mocked_celery.replace_exception_class):
            import_recent_files.delay(last_dt=arg_last_dt)
    else:
        import_recent_files.delay(last_dt=arg_last_dt)

    last_dt = arg_last_dt or tracker_last_dt
    last_dt_str = last_dt.strftime("%Y-%m-%dT%H:%M:%S.%f") if last_dt else None
    base_query = "(not trashed and not mimeType = 'application/vnd.google-apps.folder')"
    expected_query = (
        f"{base_query} and (modifiedTime > '{last_dt_str}' or createdTime > '{last_dt_str}')"
        if last_dt
        else base_query
    )

    mock_list_files.assert_called_once_with(
        query=expected_query, fields=DRIVE_FILE_FIELDS
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
                mock_transcode_task.assert_any_call(
                    LIST_VIDEO_RESPONSES[i]["files"][0]["id"]
                )
        else:  # chained tasks should be run
            mock_upload_task.assert_any_call(
                LIST_VIDEO_RESPONSES[i]["files"][0]["id"],
                prefix=settings.DRIVE_S3_UPLOAD_PREFIX,
            )
            assert (
                tracker.last_dt
                == datetime.strptime(
                    LIST_VIDEO_RESPONSES[0]["files"][0]["modifiedTime"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=pytz.utc)
            )
            mock_transcode_task.assert_any_call(
                LIST_VIDEO_RESPONSES[i]["files"][0]["id"]
            )
            mock_sync_content_task.assert_any_call(website.name)
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


def test_import_recent_files_nonvideos(settings, mocker, mocked_celery):
    """
    import_recent_files should import non-video files
    """
    mocker.patch("gdrive_sync.tasks.is_gdrive_enabled", return_value=True)
    settings.DRIVE_SHARED_ID = "test_drive"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = "parent"
    website = WebsiteFactory.create()

    parent_tree_responses = [
        [
            {
                "id": "parent",
                "name": "ancestor_exists",
            },
            {
                "id": LIST_FILE_RESPONSES[0]["files"][i]["parents"][0],
                "name": website.short_id,
            },
            {"id": "abc123", "name": DRIVE_FOLDER_FILES_FINAL},
        ]
        for i in range(2)
    ]
    mocker.patch("gdrive_sync.api.get_parent_tree", side_effect=parent_tree_responses)

    mocker.patch(
        "gdrive_sync.tasks.query_files", return_value=LIST_FILE_RESPONSES[0]["files"]
    )
    mock_upload_task = mocker.patch("gdrive_sync.tasks.stream_drive_file_to_s3.s")
    mock_resource_task = mocker.patch(
        "gdrive_sync.tasks.create_resource_from_gdrive.si"
    )

    with pytest.raises(mocked_celery.replace_exception_class):
        import_recent_files.delay(
            last_dt=datetime.strptime("2021-01-01", "%Y-%m-%d").replace(
                tzinfo=pytz.UTC
            ),
        )
        with pytest.raises(AssertionError):
            mock_upload_task.assert_any_call(
                LIST_FILE_RESPONSES[1]["files"][0]["id"],
                prefix=settings.DRIVE_S3_UPLOAD_PREFIX,
            )
        mock_upload_task.assert_any_call(
            LIST_VIDEO_RESPONSES[0]["files"][0]["id"],
            prefix=website.starter.config["root-url-path"],
        )
        mock_resource_task.assert_any_call(LIST_VIDEO_RESPONSES[0]["files"][0]["id"])


def test_create_resource_from_gdrive(mocker):
    """create_resource_from_gdrive should call create_gdrive_resource_content"""
    mocker.patch(
        "gdrive_sync.api.get_s3_content_type", return_value="application/ms-word"
    )
    mock_create_content = mocker.patch(
        "gdrive_sync.tasks.create_gdrive_resource_content"
    )
    drive_file = DriveFileFactory.create()
    create_resource_from_gdrive.delay(drive_file.file_id)
    mock_create_content.assert_called_once_with(drive_file)


def test_import_website_files(mocker, mocked_celery):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    mocker.patch("gdrive_sync.tasks.is_gdrive_enabled", return_value=True)
    website = WebsiteFactory.create()
    drive_files = DriveFileFactory.create_batch(2, website=website)
    mock_process_file_result = mocker.patch(
        "gdrive_sync.tasks.process_file_result", side_effect=drive_files
    )
    mock_stream_task = mocker.patch("gdrive_sync.tasks.stream_drive_file_to_s3.s")
    mock_create_resource = mocker.patch(
        "gdrive_sync.tasks.create_resource_from_gdrive.si"
    )
    mock_sync_content = mocker.patch("gdrive_sync.tasks.sync_website_content.si")
    mocker.patch(
        "gdrive_sync.tasks.query_files",
        side_effect=[
            [
                {
                    "id": "websiteFolderId",
                    "name": website.short_id,
                },
            ],
            [
                {
                    "id": "websiteVideoFinalFolderId",
                    "name": DRIVE_FOLDER_VIDEOS_FINAL,
                },
            ],
            [
                {
                    "id": "websiteFileFinalFolderId",
                    "name": DRIVE_FOLDER_FILES_FINAL,
                },
            ],
        ],
    )
    mocker.patch(
        "gdrive_sync.tasks.walk_gdrive_folder",
        side_effect=[[], LIST_FILE_RESPONSES[0]["files"]],
    )
    with pytest.raises(mocked_celery.replace_exception_class):
        import_website_files.delay(website.short_id)
    assert mock_process_file_result.call_count == 2
    for drive_file in drive_files:
        mock_stream_task.assert_any_call(
            drive_file.file_id, prefix=drive_file.s3_prefix
        )
        mock_create_resource.assert_any_call(drive_file.file_id)
    mock_sync_content.assert_called_once_with(website.name)


def test_import_website_files_dupe_site_folders(mocker):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    mocker.patch("gdrive_sync.tasks.is_gdrive_enabled", return_value=True)
    website = WebsiteFactory.create()
    mocker.patch(
        "gdrive_sync.tasks.query_files",
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
    mocker.patch("gdrive_sync.tasks.is_gdrive_enabled", return_value=True)
    website = WebsiteFactory.create()
    mock_log = mocker.patch("gdrive_sync.tasks.log.error")
    mocker.patch(
        "gdrive_sync.tasks.query_files",
        side_effect=[
            [
                {
                    "id": "websiteFolderId",
                    "name": website.short_id,
                },
            ],
            [],
            [],
        ],
    )
    import_website_files.delay(website.short_id)
    for folder in [DRIVE_FOLDER_VIDEOS_FINAL, DRIVE_FOLDER_FILES_FINAL]:
        mock_log.assert_any_call(
            "Expected 1 drive folder for %s/%s but found %d",
            website.short_id,
            folder,
            0,
        )
