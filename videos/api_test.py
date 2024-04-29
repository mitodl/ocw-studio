"""Test for videos.api"""

import json
from os import path

import pytest

from gdrive_sync.factories import DriveFileFactory
from videos.api import (
    create_media_convert_job,
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
    mock_boto = mocker.patch("videos.api.boto3")
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
    assert destination.startswith(
        f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{settings.VIDEO_S3_TRANSCODE_PREFIX}"
    )
    assert destination.endswith(
        path.splitext(video.source_key.split("/")[-1])[0]  # noqa: PTH122
    )  # noqa: PTH122, RUF100
    assert (
        call_kwargs["Settings"]["Inputs"][0]["FileInput"]
        == f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{video.source_key}"
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
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json",
        encoding="utf-8",
    ) as infile:
        data = json.loads(infile.read())["detail"]
    update_video_job(video_job, data)
    mock_process_outputs.assert_called_once()
    video_job.refresh_from_db()
    assert video_job.job_output == data
    assert video_job.status == VideoJobStatus.COMPLETE
    assert mock_log.call_count == (1 if raises_exception else 0)


def test_update_video_job_error(mocker):
    """The video job should be updated as expected if the transcode job failed"""
    mock_log = mocker.patch("videos.api.log.error")
    video_job = VideoJobFactory.create()
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_error.json", encoding="utf-8"
    ) as infile:
        data = json.loads(infile.read())["detail"]
    update_video_job(video_job, data)
    video_job.refresh_from_db()
    assert video_job.job_output == data
    assert video_job.error_code == str(data.get("errorCode"))
    assert video_job.error_message == data.get("errorMessage")
    assert video_job.status == VideoJobStatus.FAILED
    assert video_job.video.status == VideoStatus.FAILED
    mock_log.assert_called_once()
