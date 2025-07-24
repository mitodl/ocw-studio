"""Test for videos.api"""

import json
from os import path

import pytest
from botocore.exceptions import ClientError

from gdrive_sync.factories import DriveFileFactory
from videos.api import (
    create_media_convert_job,
    get_media_convert_job,
    prepare_job_results,
    prepare_video_download_file,
    process_video_outputs,
    update_video_job,
)
from videos.conftest import TEST_VIDEOS_WEBHOOK_PATH
from videos.constants import (
    DESTINATION_ARCHIVE,
    DESTINATION_YOUTUBE,
    VideoFileStatus,
    VideoJobStatus,
    VideoStatus,
)
from videos.factories import VideoFactory, VideoFileFactory, VideoJobFactory
from videos.models import VideoFile, VideoJob
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.factories import WebsiteContentFactory

pytestmark = pytest.mark.django_db


def test_create_media_convert_job(settings, mocker):
    """create_media_convert_job should send a request to MediaConvert, create a VideoJob object"""
    queue_name = "test_queue"
    settings.VIDEO_TRANSCODE_QUEUE = queue_name
    mock_boto = mocker.patch("mitol.transcoding.api.boto3")
    job_id = "abcd123-gh564"
    mock_boto.client.return_value.create_job.return_value = {"Job": {"Id": job_id}}
    video = VideoFactory.create()
    create_media_convert_job(video)
    mock_boto.client.return_value.create_job.assert_called_once()
    call_kwargs = mock_boto.client.return_value.create_job.call_args_list[0][1]
    assert call_kwargs["Role"] == (
        f"arn:aws:iam::{settings.AWS_ACCOUNT_ID}:role/{settings.AWS_ROLE_NAME}"
    )
    assert call_kwargs["Queue"] == (
        f"arn:aws:mediaconvert:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:queues/{queue_name}"
    )
    assert call_kwargs["UserMetadata"]["filter"] == queue_name
    destination = call_kwargs["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
        "FileGroupSettings"
    ]["Destination"]
    assert destination.endswith(
        path.splitext(video.source_key.split("/")[-1])[0]  # noqa: PTH122
    )
    assert VideoJob.objects.filter(job_id=job_id, video=video).count() == 1
    video.refresh_from_db()
    assert video.status == VideoStatus.TRANSCODING


def test_process_video_outputs(mocker):
    """Based on transcoder output, three new video files should be created"""
    mock_prepare_download = mocker.patch("videos.api.prepare_video_download_file")
    video = VideoFactory.create()
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json",
        encoding="utf-8",
    ) as infile:
        outputs = json.loads(infile.read())["detail"]["outputGroupDetails"]
        process_video_outputs(video, outputs)
        assert video.videofiles.count() == 3
        mock_prepare_download.assert_called_once_with(video)
        youtube_video = VideoFile.objects.get(
            video=video, destination=DESTINATION_YOUTUBE
        )
        assert "_youtube." in youtube_video.s3_key
        assert youtube_video.status == VideoFileStatus.CREATED
        assert youtube_video.destination_status is None
        assert youtube_video.destination_id is None
        for videofile in VideoFile.objects.filter(
            video=video, destination=DESTINATION_ARCHIVE
        ):
            assert "_youtube." not in videofile.s3_key


@pytest.mark.parametrize("files_exist", [True, False])
def test_prepare_video_download_file(settings, mocker, files_exist):
    """The correct video file S3 path should be changed, and Website.file updated"""
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_RESOURCE)
    video = VideoFactory.create(website=content.website)
    DriveFileFactory.create(website=video.website, video=video, resource=content)
    mock_move_s3 = mocker.patch("videos.api.move_s3_object")

    NEW_FILE_SIZE = 1234
    mock_fetch_content_file_size = mocker.patch("videos.api.fetch_content_file_size")
    mock_fetch_content_file_size.return_value = NEW_FILE_SIZE

    dl_video_name = "my_video__360p_16_9.mp4"
    if files_exist:
        for name in ("my_video_youtube.mp4", dl_video_name, "my_video_360p_4_3.mp4"):
            VideoFileFactory.create(
                video=video,
                s3_key=f"{settings.VIDEO_S3_TRANSCODE_PREFIX}/fakejobid/{video.website.name}/{name}",
                destination=DESTINATION_ARCHIVE,
            )
    prepare_video_download_file(video)
    content.refresh_from_db()
    if files_exist:
        mock_move_s3.assert_called_once_with(
            f"{settings.VIDEO_S3_TRANSCODE_PREFIX}/fakejobid/{video.website.name}/{dl_video_name}",
            f"{video.website.s3_path}/{dl_video_name}",
        )
        assert content.file.name == f"{video.website.s3_path}/{dl_video_name}"
        assert content.metadata["file_size"] == NEW_FILE_SIZE
    else:
        mock_move_s3.assert_not_called()
        assert content.file.name == ""


@pytest.mark.parametrize("raises_exception", [True, False])
def test_update_video_job_success(mocker, raises_exception):
    """The video job should be updated as expected if the transcode job succeeded"""
    mock_process_outputs = mocker.patch(
        "videos.api.process_video_outputs",
        side_effect=(ValueError() if raises_exception else None),
    )
    mock_log = mocker.patch("videos.api.log.exception")
    video_job = VideoJobFactory.create(status=VideoJobStatus.CREATED)
    mock_job = mocker.patch("videos.api.VideoJob.objects.get")
    mock_job.return_value = video_job
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json",
        encoding="utf-8",
    ) as infile:
        data = json.loads(infile.read())["detail"]
    update_video_job(data)
    mock_process_outputs.assert_called_once()
    video_job.refresh_from_db()
    assert video_job.job_output == data
    assert video_job.status == VideoJobStatus.COMPLETE
    assert mock_log.call_count == (1 if raises_exception else 0)


def test_update_video_job_error(mocker):
    """The video job should be updated as expected if the transcode job failed"""
    mock_log = mocker.patch("videos.api.log.error")
    video_job = VideoJobFactory.create()
    mock_job = mocker.patch("videos.api.VideoJob.objects.get")
    mock_job.return_value = video_job
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_error.json", encoding="utf-8"
    ) as infile:
        data = json.loads(infile.read())["detail"]
    update_video_job(data)
    video_job.refresh_from_db()
    assert video_job.job_output == data
    assert video_job.error_code == str(data.get("errorCode"))
    assert video_job.error_message == data.get("errorMessage")
    assert video_job.status == VideoJobStatus.FAILED
    assert video_job.video.status == VideoStatus.FAILED
    mock_log.assert_called_once()


def test_update_video_job_unknown_status(mocker):
    """The video job should handle unknown status gracefully"""
    video_job = VideoJobFactory.create(status=VideoJobStatus.CREATED)
    mock_job = mocker.patch("videos.api.VideoJob.objects.get")
    mock_job.return_value = video_job

    # Create mock data with unknown status
    data = {
        "jobId": video_job.job_id,
        "status": "UNKNOWN_STATUS",
        "outputGroupDetails": [],
    }

    update_video_job(data)
    video_job.refresh_from_db()

    # Should update job_output but not change status since it's unknown
    assert video_job.job_output == data
    assert video_job.status == VideoJobStatus.CREATED  # Should remain unchanged


def test_update_video_job_missing_output_group_details(mocker):
    """The video job should handle missing outputGroupDetails gracefully"""
    video_job = VideoJobFactory.create(status=VideoJobStatus.CREATED)
    mock_job = mocker.patch("videos.api.VideoJob.objects.get")
    mock_job.return_value = video_job

    # Create mock data without outputGroupDetails
    data = {"jobId": video_job.job_id, "status": "COMPLETE"}

    mock_process_outputs = mocker.patch("videos.api.process_video_outputs")

    update_video_job(data)
    video_job.refresh_from_db()

    # Should still call process_video_outputs even with empty outputGroupDetails
    mock_process_outputs.assert_called_once_with(video_job.video, [])
    assert video_job.status == VideoJobStatus.COMPLETE


def test_update_video_job_empty_error_details(mocker):
    """The video job should handle missing error details in error status"""
    video_job = VideoJobFactory.create(status=VideoJobStatus.CREATED)
    mock_job = mocker.patch("videos.api.VideoJob.objects.get")
    mock_job.return_value = video_job
    mock_log = mocker.patch("videos.api.log.error")

    # Create mock data with error status but no error details
    data = {"jobId": video_job.job_id, "status": "ERROR"}

    update_video_job(data)
    video_job.refresh_from_db()

    assert video_job.status == VideoJobStatus.FAILED
    assert video_job.video.status == VideoStatus.FAILED
    assert video_job.error_code == "None"  # str(None)
    assert video_job.error_message is None
    mock_log.assert_called_once()


def test_update_video_job_case_insensitive_status(mocker):
    """The video job should handle case-insensitive status matching"""
    video_job = VideoJobFactory.create(status=VideoJobStatus.CREATED)
    mock_job = mocker.patch("videos.api.VideoJob.objects.get")
    mock_job.return_value = video_job

    test_cases = ["complete", "COMPLETE", "Complete", "error", "ERROR", "Error"]

    for status in test_cases:
        video_job.status = VideoJobStatus.CREATED
        video_job.save()

        data = {"jobId": video_job.job_id, "status": status, "outputGroupDetails": []}

        update_video_job(data)
        video_job.refresh_from_db()

        if status.lower() == "complete":
            assert video_job.status == VideoJobStatus.COMPLETE
        elif status.lower() == "error":
            assert video_job.status == VideoJobStatus.FAILED
            assert video_job.video.status == VideoStatus.FAILED


def test_get_media_convert_job(settings, mocker):
    """get_media_convert_job should return MediaConvert job details"""
    job_id = "test_job_id"
    mock_boto = mocker.patch("videos.api.boto3")
    mock_job_data = {
        "Job": {
            "Id": job_id,
            "Status": "COMPLETE",
            "Settings": {},
        }
    }
    mock_boto.client.return_value.get_job.return_value = mock_job_data

    result = get_media_convert_job(job_id)

    mock_boto.client.assert_called_once_with(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
    )
    mock_boto.client.return_value.get_job.assert_called_once_with(Id=job_id)
    assert result == mock_job_data


def test_get_media_convert_job_client_error(settings, mocker):
    """get_media_convert_job should handle AWS client errors gracefully"""
    job_id = "test_job_id"
    mock_boto = mocker.patch("videos.api.boto3")
    mock_boto.client.return_value.get_job.side_effect = ClientError(
        {"Error": {"Code": "JobNotFound", "Message": "Job not found"}}, "GetJob"
    )

    with pytest.raises(ClientError):
        get_media_convert_job(job_id)

    mock_boto.client.assert_called_once_with(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
    )


@pytest.mark.parametrize(
    "missing_setting",
    [
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "VIDEO_S3_TRANSCODE_ENDPOINT",
    ],
)
def test_get_media_convert_job_missing_settings(settings, mocker, missing_setting):
    """get_media_convert_job should handle missing AWS settings"""
    job_id = "test_job_id"

    # Remove the setting
    delattr(settings, missing_setting)

    mock_boto = mocker.patch("videos.api.boto3")

    # This should still work as boto3 client handles missing values gracefully
    # by using None or defaults
    get_media_convert_job(job_id)

    mock_boto.client.assert_called_once()


def test_prepare_job_results(settings):
    """prepare_job_results should replace template placeholders with actual values"""
    video = VideoFactory.create()
    # Set a proper source_key format for testing DRIVE_FILE_ID extraction
    video.source_key = "gdrive_uploads/test_short_id/test_drive_file_id/test_video.mp4"
    video.save()
    video_job = VideoJobFactory.create(video=video)

    # Set up required settings
    settings.AWS_ACCOUNT_ID = "123456789"
    settings.AWS_REGION = "us-east-1"
    settings.VIDEO_TRANSCODE_QUEUE = "test-queue"
    settings.VIDEO_S3_TRANSCODE_BUCKET = "test-bucket"
    settings.VIDEO_S3_TRANSCODE_PREFIX = "test-prefix"

    template_results = """
    {
      "jobId": "<VIDEO_JOB_ID>",
      "status": "COMPLETE",
      "accountId": "<AWS_ACCOUNT_ID>",
      "region": "<AWS_REGION>",
      "queue": "<VIDEO_TRANSCODE_QUEUE>",
      "bucket": "<VIDEO_S3_TRANSCODE_BUCKET>",
      "prefix": "<VIDEO_S3_TRANSCODE_PREFIX>",
      "shortId": "<SHORT_ID>",
      "driveFileId": "<DRIVE_FILE_ID>",
      "videoName": "<VIDEO_NAME>"
    }
    """

    result = prepare_job_results(video, video_job, template_results)

    assert result["jobId"] == video_job.job_id
    assert result["accountId"] == settings.AWS_ACCOUNT_ID
    assert result["region"] == settings.AWS_REGION
    assert result["queue"] == settings.VIDEO_TRANSCODE_QUEUE
    assert result["bucket"] == settings.VIDEO_S3_TRANSCODE_BUCKET
    assert result["prefix"] == settings.VIDEO_S3_TRANSCODE_PREFIX
    assert result["shortId"] == video.website.short_id
    assert result["driveFileId"] == "test_drive_file_id"
    assert result["videoName"] == "video"


def test_prepare_job_results_invalid_json(mocker):
    """prepare_job_results should handle invalid JSON gracefully"""
    mock_log = mocker.patch("videos.api.log.exception")
    video = VideoFactory.create()
    video_job = VideoJobFactory.create(video=video)

    invalid_json = "{ invalid json }"

    result = prepare_job_results(video, video_job, invalid_json)

    assert result == {}
    mock_log.assert_called_once_with("Failed to decode MediaConvert job results")


def test_prepare_job_results_missing_settings(settings):
    """prepare_job_results should handle missing settings gracefully"""
    video = VideoFactory.create()
    video_job = VideoJobFactory.create(video=video)

    # Remove some settings
    delattr(settings, "AWS_ACCOUNT_ID")
    delattr(settings, "VIDEO_TRANSCODE_QUEUE")

    template_results = """
    {
      "jobId": "<VIDEO_JOB_ID>",
      "accountId": "<AWS_ACCOUNT_ID>",
      "queue": "<VIDEO_TRANSCODE_QUEUE>"
    }
    """

    result = prepare_job_results(video, video_job, template_results)

    assert result["jobId"] == video_job.job_id
    # Missing settings should be replaced with empty strings
    assert result["accountId"] == ""
    assert result["queue"] == ""


def test_prepare_job_results_empty_template():
    """prepare_job_results should handle empty template gracefully"""
    video = VideoFactory.create()
    video_job = VideoJobFactory.create(video=video)

    empty_template = ""
    result = prepare_job_results(video, video_job, empty_template)

    assert result == {}


def test_prepare_job_results_malformed_json():
    """prepare_job_results should handle malformed JSON beyond just invalid syntax"""
    video = VideoFactory.create()
    video_job = VideoJobFactory.create(video=video)

    # JSON with unmatched braces after template replacement
    malformed_template = '{"jobId": "<VIDEO_JOB_ID>", "data": {'

    result = prepare_job_results(video, video_job, malformed_template)

    assert result == {}


@pytest.mark.parametrize(
    "template_placeholders",
    [
        ("<VIDEO_JOB_ID>", "job_id_value"),
        ("<SHORT_ID>", "short_id_value"),
        ("<DRIVE_FILE_ID>", "drive_file_id_value"),
        ("<VIDEO_NAME>", "video"),
    ],
)
def test_prepare_job_results_individual_placeholders(settings, template_placeholders):
    """Test that individual placeholders are correctly replaced"""
    video = VideoFactory.create()
    video.website.short_id = "short_id_value"
    video.website.save()
    # Set a proper source_key format for testing DRIVE_FILE_ID extraction
    video.source_key = (
        "gdrive_uploads/short_id_value/drive_file_id_value/test_video.mp4"
    )
    video.save()
    video_job = VideoJobFactory.create(video=video, job_id="job_id_value")

    placeholder, expected_value = template_placeholders
    template = f'{{"test": "{placeholder}"}}'

    result = prepare_job_results(video, video_job, template)

    if placeholder == "<DRIVE_FILE_ID>":
        # Extract drive file ID from source_key (second to last part)
        try:
            source_key_parts = video.source_key.split("/")
            expected_value = source_key_parts[-2] if len(source_key_parts) >= 3 else ""
        except (AttributeError, IndexError):
            expected_value = ""
    elif placeholder == "<SHORT_ID>":
        expected_value = video.website.short_id
    elif placeholder == "<VIDEO_JOB_ID>":
        expected_value = video_job.job_id

    assert result["test"] == expected_value


def test_process_video_outputs_empty_output_group(mocker):
    """process_video_outputs should handle empty output group gracefully"""
    mock_prepare_download = mocker.patch("videos.api.prepare_video_download_file")
    video = VideoFactory.create()

    # Test with empty output group details list
    process_video_outputs(video, [])

    # Should not call prepare_video_download_file when output group is empty
    mock_prepare_download.assert_not_called()
    assert video.videofiles.count() == 0


def test_process_video_outputs_malformed_paths(mocker):
    """process_video_outputs should handle malformed S3 paths gracefully"""
    mock_prepare_download = mocker.patch("videos.api.prepare_video_download_file")
    video = VideoFactory.create()

    # Test with malformed S3 paths
    malformed_outputs = [
        {
            "outputDetails": [
                {
                    "outputFilePaths": [
                        "invalid-path-without-s3-prefix",
                        "s3://",  # Empty path after s3://
                        "s3://bucket/",  # Path with only bucket
                    ]
                }
            ]
        }
    ]

    process_video_outputs(video, malformed_outputs)

    # Should create at least one VideoFile object despite malformed paths
    # Due to unique constraint on s3_key, multiple empty/same keys result in only one object
    assert video.videofiles.count() >= 1
    mock_prepare_download.assert_called_once_with(video)


@pytest.mark.parametrize("file_extension", [".mp4", ".mov", ".avi", ".webm", ""])
def test_process_video_outputs_various_extensions(mocker, file_extension):
    """process_video_outputs should handle various file extensions"""
    mock_prepare_download = mocker.patch("videos.api.prepare_video_download_file")
    video = VideoFactory.create()

    outputs = [
        {
            "outputDetails": [
                {
                    "outputFilePaths": [
                        f"s3://bucket/path/video_youtube{file_extension}",
                        f"s3://bucket/path/video_archive{file_extension}",
                    ]
                }
            ]
        }
    ]

    process_video_outputs(video, outputs)

    assert video.videofiles.count() == 2

    # Check destinations are correctly assigned based on filename
    youtube_files = video.videofiles.filter(destination=DESTINATION_YOUTUBE)
    archive_files = video.videofiles.filter(destination=DESTINATION_ARCHIVE)

    assert youtube_files.count() == 1
    assert archive_files.count() == 1
    assert "youtube" in youtube_files.first().s3_key
    assert "archive" in archive_files.first().s3_key

    mock_prepare_download.assert_called_once_with(video)
