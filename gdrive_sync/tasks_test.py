"""Tests for gdrive_sync tasks"""

import pytest
from mitol.common.utils import now_in_utc
from moto import mock_s3

from gdrive_sync import tasks
from gdrive_sync.conftest import LIST_FILE_RESPONSES
from gdrive_sync.constants import (
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    WebsiteSyncStatus,
)
from gdrive_sync.factories import DriveFileFactory
from gdrive_sync.tasks import (
    create_gdrive_folders_batch,
    create_gdrive_resource_content_batch,
    delete_drive_file,
    import_website_files,
    populate_file_sizes,
    populate_file_sizes_bulk,
    process_drive_file,
    update_website_status,
)
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name


@pytest.fixture()
def mock_gdrive_files(mocker):  # noqa: PT004
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
    """Folder should be created if settings are present"""
    settings.DRIVE_SHARED_ID = shared_id
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_creds
    mock_create_folder = mocker.patch("gdrive_sync.tasks.api.create_gdrive_folders")
    tasks.create_gdrive_folders.delay("test")
    assert mock_create_folder.call_count == (1 if shared_id and drive_creds else 0)


@pytest.mark.parametrize(("chunk_size", "chunks"), [[3, 1], [2, 2]])  # noqa: PT007
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


def test_import_website_files(mocker, mocked_celery, mock_gdrive_files):  # pylint:disable=unused-argument
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


def test_import_website_files_processing_error(mocker, mock_gdrive_files):  # pylint:disable=unused-argument
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


def test_import_website_files_delete_missing(mocker, mocked_celery):
    """Missing files should be deleted on sync"""
    mocker.patch("gdrive_sync.tasks.api.is_gdrive_enabled", return_value=True)
    website = WebsiteFactory.create()
    drive_files = DriveFileFactory.create_batch(2, website=website)
    mock_delete_drive_file = mocker.patch("gdrive_sync.tasks.delete_drive_file.si")
    with pytest.raises(mocked_celery.replace_exception_class):
        import_website_files.delay(website.name)
    assert mock_delete_drive_file.call_count == 2
    for drive_file in drive_files:
        mock_delete_drive_file.assert_any_call(drive_file.file_id, mocker.ANY)


def test_update_website_status(mocker):
    """Calling the update_website_status task should call api.update_sync_status with args"""
    website = WebsiteFactory.create()
    now = now_in_utc()
    mock_update_sync_status = mocker.patch("gdrive_sync.tasks.api.update_sync_status")
    update_website_status.delay(website.pk, now)
    mock_update_sync_status.assert_called_once_with(website, now)


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

    mock_log = mocker.patch("gdrive_sync.tasks.log.exception")
    process_drive_file.delay(drive_file.file_id)
    assert mock_stream_s3.call_count == 1
    assert mock_transcode.call_count == (1 if is_video and not has_error else 0)
    assert mock_log.call_count == (1 if has_error else 0)


@pytest.mark.parametrize("drive_file_count", [0, 5])
def test_create_gdrive_resource_content_batch(mocker, drive_file_count):
    """This batch task should call create_gdrive_resource_content for each valid file."""
    mock_create_resource = mocker.patch(
        "gdrive_sync.tasks.api.create_gdrive_resource_content"
    )

    drive_files = DriveFileFactory.create_batch(drive_file_count)
    drive_file_ids = [drive_file.file_id for drive_file in drive_files] + [
        None,
        "an_id_that_does_not_exist",
    ]

    create_gdrive_resource_content_batch.delay(drive_file_ids)
    assert mock_create_resource.call_count == len(drive_files)
    for drive_file in drive_files:
        mock_create_resource.assert_any_call(drive_file)


def test_delete_drive_file(mocker):
    """Task delete_drive_file should delegate the delete action to api.delete_drive_file."""
    drive_file = DriveFileFactory.create()
    mock_delete_drive_file = mocker.patch("gdrive_sync.api.delete_drive_file")
    delete_drive_file.delay(drive_file.file_id, drive_file.website.synced_on)
    mock_delete_drive_file.assert_called_once_with(
        drive_file, sync_datetime=drive_file.website.synced_on
    )


@mock_s3
@pytest.mark.parametrize("override_existing", [True, False])
def test_populate_file_sizes_for_content(settings, mocker, override_existing):
    """populate_file_sizes should populate file sizes for website's content."""
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"

    NEW_FILE_SIZE = 1234
    mock_fetch_content_file_size = mocker.patch(
        "gdrive_sync.utils.fetch_content_file_size"
    )
    mock_fetch_content_file_size.return_value = NEW_FILE_SIZE

    website = WebsiteFactory.create()

    contents = WebsiteContentFactory.create_batch(
        2, website=website, type=CONTENT_TYPE_RESOURCE, metadata={}
    )
    existing_size_contents = WebsiteContentFactory.create_batch(
        2, website=website, type=CONTENT_TYPE_RESOURCE, metadata={"file_size": 321}
    )

    populate_file_sizes.delay(website.name, override_existing)

    for content in contents:
        content.refresh_from_db()
        assert content.metadata["file_size"] == NEW_FILE_SIZE

    for content in existing_size_contents:
        content.refresh_from_db()
        assert (
            content.metadata["file_size"] == NEW_FILE_SIZE
            if override_existing
            else content.metadata["file_size"] is not None
            and content.metadata["file_size"] != NEW_FILE_SIZE
        )


@mock_s3
@pytest.mark.parametrize("override_existing", [True, False])
def test_populate_file_sizes_for_drive_file(settings, mocker, override_existing):
    """populate_file_sizes should populate file sizes for drive files associated with content."""
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"

    NEW_FILE_SIZE = 1234
    mock_fetch_content_file_size = mocker.patch(
        "gdrive_sync.utils.fetch_drive_file_size"
    )
    mock_fetch_content_file_size.return_value = NEW_FILE_SIZE

    website = WebsiteFactory.create()

    content = WebsiteContentFactory.create(
        website=website, type=CONTENT_TYPE_RESOURCE, metadata={}
    )

    drive_files = [
        DriveFileFactory.create(resource=content, website=website, size=None),
        DriveFileFactory.create(resource=content, website=website, size=None),
    ]
    existing_size_drive_files = [
        DriveFileFactory.create(resource=content, website=website, size=321),
        DriveFileFactory.create(resource=content, website=website, size=321),
    ]

    populate_file_sizes.delay(website.name, override_existing)

    for drive_file in drive_files:
        drive_file.refresh_from_db()
        assert drive_file.size == NEW_FILE_SIZE

    for drive_file in existing_size_drive_files:
        drive_file.refresh_from_db()
        assert (
            drive_file.size == NEW_FILE_SIZE
            if override_existing
            else drive_file.size is not None and drive_file.size != NEW_FILE_SIZE
        )


@pytest.mark.parametrize("override_existing", [True, False])
def test_populate_file_sizes_bulk_delegates(mocker, mocked_celery, override_existing):
    """Task populate_file_sizes_bulk should delegate each website to a populate_file_sizes task."""
    mock_populate_file_sizes = mocker.patch("gdrive_sync.tasks.populate_file_sizes.si")
    websites = WebsiteFactory.create_batch(3)
    website_names = [website.name for website in websites]
    with pytest.raises(mocked_celery.replace_exception_class):
        populate_file_sizes_bulk.delay(website_names, override_existing)

    assert mock_populate_file_sizes.call_count == 3
    for name in website_names:
        mock_populate_file_sizes.assert_any_call(name, override_existing)
