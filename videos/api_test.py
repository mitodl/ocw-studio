"""Test for videos.api"""
import json
from os import path

import pytest

from gdrive_sync.factories import DriveFileFactory
from videos.api import (
    create_media_convert_job,
    prepare_video_download_file,
    process_video_outputs,
)
from videos.conftest import TEST_VIDEOS_WEBHOOK_PATH
from videos.constants import (
    DESTINATION_ARCHIVE,
    DESTINATION_YOUTUBE,
    VideoFileStatus,
    VideoStatus,
)
from videos.factories import VideoFactory, VideoFileFactory
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
    assert destination.endswith(path.splitext(video.source_key.split("/")[-1])[0])
    assert (
        call_kwargs["Settings"]["Inputs"][0]["FileInput"]
        == f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{video.source_key}"
    )
    assert VideoJob.objects.filter(job_id=job_id, video=video).count() == 1
    video.refresh_from_db()
    assert video.status == VideoStatus.TRANSCODING


def test_process_video_outputs(mocker):
    """ Based on transcoder output, three new video files should be created"""
    mock_prepare_download = mocker.patch("videos.api.prepare_video_download_file")
    video = VideoFactory.create()
    with open(
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json", "r"
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


def test_prepare_video_download_file(settings, mocker):
    """The correct video file S3 path should be changed, and Website.file updated"""
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_RESOURCE)
    video = VideoFactory.create(website=content.website)
    DriveFileFactory.create(website=video.website, video=video, resource=content)
    mock_move_s3 = mocker.patch("videos.api.move_s3_object")
    dl_video_name = "my_video__360p_16_9.mp4"
    for name in ("my_video_youtube.mp4", dl_video_name, "my_video_360p_4_3.mp4"):
        VideoFileFactory.create(
            video=video,
            s3_key=f"{settings.VIDEO_S3_TRANSCODE_PREFIX}/fakejobid/{video.website.name}/{name}",
            destination=DESTINATION_ARCHIVE,
        )
    prepare_video_download_file(video)
    mock_move_s3.assert_called_once_with(
        f"{settings.VIDEO_S3_TRANSCODE_PREFIX}/fakejobid/{video.website.name}/{dl_video_name}",
        f"sites/{video.website.name}/{dl_video_name}",
    )
    content.refresh_from_db()
    assert content.file.name == f"sites/{video.website.name}/{dl_video_name}"
