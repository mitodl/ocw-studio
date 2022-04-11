"""Tests for gdrive_sync tasks"""
from datetime import datetime

import pytest
import pytz
from mitol.common.utils import now_in_utc

from gdrive_sync import tasks
from gdrive_sync.conftest import LIST_FILE_RESPONSES, LIST_VIDEO_RESPONSES
from gdrive_sync.constants import (
    DRIVE_API_FILES,
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DriveFileStatus,
    WebsiteSyncStatus,
)
from gdrive_sync.factories import DriveApiQueryTrackerFactory, DriveFileFactory
from gdrive_sync.models import DriveFile
from gdrive_sync.tasks import (
    create_gdrive_folders_batch,
    import_recent_files,
    import_website_files,
    process_drive_file,
    update_website_status,
)
from websites.factories import WebsiteFactory


pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@pytest.fixture()
def mock_gdrive_files(mocker):
    """Return mock results from a google drive api request"""
    mocker.patch(
        "gdrive_sync.tasks.api.query_files",
        side_effect=[
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
        "gdrive_sync.tasks.api.walk_gdrive_folder",
        side_effect=[[], LIST_FILE_RESPONSES[0]["files"]],
    )


@pytest.mark.parametrize("shared_id", [None, "testDrive"])
@pytest.mark.parametrize("drive_creds", [None, '{"key": "value"}'])
def test_create_gdrive_folders(settings, mocker, shared_id, drive_creds):
    """ Folder should be created if settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_create_folder = mocker.patch("gdrive_sync.tasks.api.create_gdrive_folders")
    tasks.create_gdrive_folders.delay("test")
    assert mock_create_folder.call_count == (1 if shared_id and drive_creds else 0)


@pytest.mark.parametrize("chunk_size, chunks", [[3, 1], [2, 2]])
def test_create_gdrive_folders_chunked(  # pylint:disable=unused-argument
    mocker, mocked_celery, chunk_size, chunks
):
    """create_gdrive_folders_chunked calls create_gdrive_folders_batch with correct arguments"""
    websites = WebsiteFactory.create_batch(3)
    short_ids = sorted([website.short_id for website in websites])
    mock_batch = mocker.patch("gdrive_sync.tasks.create_gdrive_folders_batch.s")
    with pytest.raises(TabError):
        tasks.create_gdrive_folders_chunked.delay(
            short_ids,
            chunk_size=chunk_size,
        )
    mock_batch.assert_any_call(short_ids[0:chunk_size])
    if chunks > 1:
        mock_batch.assert_any_call(short_ids[chunk_size:])


def test_create_gdrive_folders_batch(mocker):
    """create_gdrive_folders should make the expected function calls"""
    mock_create_gdrive_folders = mocker.patch(
        "gdrive_sync.tasks.api.create_gdrive_folders"
    )
    websites = WebsiteFactory.create_batch(2)
    short_ids = sorted([website.short_id for website in websites])
    tasks.create_gdrive_folders_batch.delay(short_ids)
    for short_id in short_ids:
        mock_create_gdrive_folders.assert_any_call(short_id)


@pytest.mark.parametrize("has_error", [True, False])
def test_create_gdrive_folders_batch_errors(mocker, has_error):
    """create_gdrive_folders_batch should return a list of short_ids that errored, or True if no errors"""
    short_ids = sorted([website.short_id for website in WebsiteFactory.create_batch(2)])
    side_effects = [None, Exception("api error")] if has_error else [None, None]
    mocker.patch(
        "gdrive_sync.tasks.api.create_gdrive_folders", side_effect=side_effects
    )
    result = create_gdrive_folders_batch(sorted(short_ids))
    assert result == ([short_ids[1]] if has_error else True)


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
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
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
        status=DriveFileStatus.COMPLETE,
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
        "gdrive_sync.tasks.api.query_files",
        return_value=LIST_VIDEO_RESPONSES[0]["files"]
        + LIST_VIDEO_RESPONSES[1]["files"],
    )
    mock_process_func = mocker.patch("gdrive_sync.tasks.process_drive_file.s")
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
                assert mock_process_func.assert_any_call(
                    LIST_VIDEO_RESPONSES[i]["files"][0]["id"]
                )
        else:  # chained tasks should be run
            mock_process_func.assert_any_call(LIST_VIDEO_RESPONSES[i]["files"][0]["id"])
            assert (
                tracker.last_dt
                == datetime.strptime(
                    LIST_VIDEO_RESPONSES[0]["files"][0]["modifiedTime"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=pytz.utc)
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


@pytest.mark.parametrize("raises_exception", [True, False])
def test_import_recent_files_nonvideos(
    settings, mocker, mocked_celery, raises_exception
):
    """
    import_recent_files should import non-video files
    """
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
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
        "gdrive_sync.tasks.api.query_files",
        return_value=LIST_FILE_RESPONSES[0]["files"],
    )

    side_effect = (
        [Exception(), Exception()]
        if raises_exception
        else [
            DriveFileFactory.create(file_id=LIST_FILE_RESPONSES[0]["files"][0]["id"]),
            None,
        ]
    )
    mocker.patch("gdrive_sync.tasks.api.process_file_result", side_effect=side_effect)
    mock_process_drive_file_task = mocker.patch(
        "gdrive_sync.tasks.process_drive_file.s"
    )
    mock_log = mocker.patch("gdrive_sync.tasks.log.exception")

    if not raises_exception:
        with pytest.raises(mocked_celery.replace_exception_class):
            import_recent_files.delay(
                last_dt=datetime.strptime("2021-01-01", "%Y-%m-%d").replace(
                    tzinfo=pytz.UTC
                ),
            )
    else:
        import_recent_files.delay(
            last_dt=datetime.strptime("2021-01-01", "%Y-%m-%d").replace(
                tzinfo=pytz.UTC
            ),
        )
    with pytest.raises(AssertionError):
        mock_process_drive_file_task.assert_any_call(
            LIST_VIDEO_RESPONSES[1]["files"][0]["id"]
        )
    if not raises_exception:
        mock_process_drive_file_task.assert_any_call(
            LIST_FILE_RESPONSES[0]["files"][0]["id"]
        )
    assert mock_log.call_count == (
        len(LIST_FILE_RESPONSES[0]["files"]) if raises_exception else 0
    )


def test_import_recent_files_disabled(mocker, settings):
    """import_recent_files should do nothing if google drive integration is disabled"""
    settings.DRIVE_SHARED_ID = None
    mock_query = mocker.patch("gdrive_sync.tasks.api.query_files")
    import_recent_files.delay()
    mock_query.assert_not_called()


def test_import_website_files(
    mocker, mocked_celery, mock_gdrive_files
):  # pylint:disable=unused-argument
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
    website = WebsiteFactory.create()
    drive_files = DriveFileFactory.create_batch(2, website=website)
    mock_process_file_result = mocker.patch(
        "gdrive_sync.tasks.api.process_file_result", side_effect=drive_files
    )
    mock_process_gdrive_file = mocker.patch("gdrive_sync.tasks.process_drive_file.s")
    mock_sync_content = mocker.patch("gdrive_sync.tasks.sync_website_content.si")
    mock_update_status = mocker.patch("gdrive_sync.tasks.update_website_status.si")
    with pytest.raises(mocked_celery.replace_exception_class):
        import_website_files.delay(website.name)
    assert mock_process_file_result.call_count == 2
    for drive_file in drive_files:
        mock_process_gdrive_file.assert_any_call(drive_file.file_id)
    mock_sync_content.assert_called_once_with(website.name)
    website.refresh_from_db()
    mock_update_status.assert_called_once_with(website.pk, website.synced_on)


def test_import_website_files_missing_folder(mocker):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
    website = WebsiteFactory.create()
    mock_log = mocker.patch("gdrive_sync.tasks.log.error")
    mocker.patch(
        "gdrive_sync.tasks.api.query_files",
        side_effect=[
            [],
            [],
        ],
    )
    import_website_files.delay(website.name)
    for folder in [DRIVE_FOLDER_VIDEOS_FINAL, DRIVE_FOLDER_FILES_FINAL]:
        mock_log.assert_any_call(
            "%s for %s", f"Could not find drive subfolder {folder}", website.short_id
        )
    website.refresh_from_db()
    assert website.sync_status == WebsiteSyncStatus.FAILED
    assert sorted(website.sync_errors) == sorted(
        [
            f"Could not find drive subfolder {DRIVE_FOLDER_VIDEOS_FINAL}",
            f"Could not find drive subfolder {DRIVE_FOLDER_FILES_FINAL}",
        ]
    )


def test_import_website_files_query_error(mocker):
    """import_website_files should run process_file_result for each drive file and trigger tasks"""
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
    mock_log = mocker.patch("gdrive_sync.tasks.log.exception")
    mocker.patch(
        "gdrive_sync.tasks.api.query_files",
        side_effect=Exception("Error querying google drive"),
    )
    website = WebsiteFactory.create()
    import_website_files.delay(website.name)
    sync_errors = []
    for folder in [DRIVE_FOLDER_VIDEOS_FINAL, DRIVE_FOLDER_FILES_FINAL]:
        sync_error = (
            f"An error occurred when querying the {folder} google drive subfolder"
        )
        sync_errors.append(sync_error)
        mock_log.assert_any_call("%s for %s", sync_error, website.short_id)
    website.refresh_from_db()
    assert website.sync_status == WebsiteSyncStatus.FAILED
    assert sorted(website.sync_errors) == sorted(sync_errors)


def test_import_website_files_processing_error(
    mocker, mock_gdrive_files
):  # pylint:disable=unused-argument
    """import_website_files should log exceptions raised by process_file_result and update website status"""
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
    mock_log = mocker.patch("gdrive_sync.tasks.log.exception")
    mocker.patch(
        "gdrive_sync.tasks.api.process_file_result",
        side_effect=Exception("Error processing the file"),
    )
    website = WebsiteFactory.create()
    import_website_files.delay(website.name)
    sync_errors = []
    for gdfile in LIST_FILE_RESPONSES[0]["files"]:
        sync_errors.append(f"Error processing gdrive file {gdfile.get('name')}")
        mock_log.assert_any_call(
            "Error processing gdrive file %s for %s",
            gdfile.get("name"),
            website.short_id,
        )
    website.refresh_from_db()
    assert website.sync_status == WebsiteSyncStatus.FAILED
    assert sorted(website.sync_errors) == sorted(sync_errors)


def test_update_website_status(mocker):
    """Calling the update_website_status task should call api.update_sync_status with args"""
    website = WebsiteFactory.create()
    now = now_in_utc()
    mock_update_sync_status = mocker.patch("gdrive_sync.tasks.api.update_sync_status")
    update_website_status.delay(website.pk, now)
    mock_update_sync_status.assert_called_once_with(
        website, now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


@pytest.mark.parametrize("has_error", [True, False])
@pytest.mark.parametrize("is_video", [True, False])
def test_process_drive_file(mocker, is_video, has_error):
    """The necessary steps should be run to process a google drive file"""
    drive_file = DriveFileFactory.create(
        drive_path=(
            DRIVE_FOLDER_VIDEOS_FINAL if is_video else DRIVE_FOLDER_FILES_FINAL
        ),
        mime_type="video/mp4",
    )
    mock_stream_s3 = mocker.patch(
        "gdrive_sync.tasks.api.stream_to_s3",
        side_effect=[(Exception("No bucket") if has_error else None)],
    )
    mock_transcode = mocker.patch("gdrive_sync.tasks.api.transcode_gdrive_video")
    mock_create_resource = mocker.patch(
        "gdrive_sync.tasks.api.create_gdrive_resource_content"
    )
    mock_log = mocker.patch("gdrive_sync.tasks.log.exception")
    process_drive_file.delay(drive_file.file_id)
    assert mock_stream_s3.call_count == 1
    assert mock_transcode.call_count == (1 if is_video and not has_error else 0)
    assert mock_create_resource.call_count == (0 if has_error else 1)
    assert mock_log.call_count == (1 if has_error else 0)
