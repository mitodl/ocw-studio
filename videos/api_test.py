"""Test for videos.api"""
import json
from os import path

import pytest

from videos.api import create_media_convert_job, process_video_outputs
from videos.conftest import TEST_VIDEOS_WEBHOOK_PATH
from videos.constants import DESTINATION_ARCHIVE, DESTINATION_YOUTUBE, VideoStatus
from videos.factories import VideoFactory
from videos.models import VideoFile, VideoJob


pytestmark = pytest.mark.django_db


def test_create_media_convert_job(settings, mocker):
    """create_media_convert_job should send a request to MediaConvert, create a VideoJob object"""
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


def test_process_video_outputs():
    """ Based on transcoder output, three new video files should be created"""
    video = VideoFactory.create()
    with open(
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json", "r"
    ) as infile:
        outputs = json.loads(infile.read())["detail"]["outputGroupDetails"]
        process_video_outputs(video, outputs)
        assert video.videofiles.count() == 3
        youtube_video = VideoFile.objects.get(
            video=video, destination=DESTINATION_YOUTUBE
        )
        assert "_youtube." in youtube_video.s3_key
        for videofile in VideoFile.objects.filter(
            video=video, destination=DESTINATION_ARCHIVE
        ):
            assert "_youtube." not in videofile.s3_key
