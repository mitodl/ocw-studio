"""Tests for videos.views"""
import json
from types import SimpleNamespace

import pytest
from django.urls import reverse

from gdrive_sync.factories import DriveFileFactory
from videos.conftest import TEST_VIDEOS_WEBHOOK_PATH
from videos.constants import DESTINATION_YOUTUBE, VideoStatus
from videos.factories import VideoFactory, VideoJobFactory
from websites.factories import WebsiteFactory


# pylint:disable=redefined-outer-name
pytestmark = pytest.mark.django_db


@pytest.fixture
def video_group(settings):
    """ Collection of model objects for testing video views"""
    drive_file_id = "abc123"
    drive_file_name = "testvid.avi"
    website = WebsiteFactory.create()
    video = VideoFactory.create(
        source_key=f"{settings.DRIVE_S3_UPLOAD_PREFIX}/{website.short_id}/{drive_file_id}/{drive_file_name}",
        status=VideoStatus.TRANSCODING,
    )
    video_job = VideoJobFactory.create(
        video=video,
    )
    drive_file = DriveFileFactory.create(
        file_id=drive_file_id,
        name=drive_file_name,
        video=video,
        s3_key=video.source_key,
    )
    return SimpleNamespace(video=video, video_job=video_job, drive_file=drive_file)


def test_transcode_jobs_success(settings, drf_client, video_group):
    """TranscodeJobView should process MediaConvert success notification appropriately"""
    video = video_group.video
    video_job = video_group.video_job
    with open(
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json", "r"
    ) as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", settings.AWS_ACCOUNT_ID)
            .replace("AWS_REGION", settings.AWS_REGION)
            .replace("AWS_BUCKET", settings.AWS_STORAGE_BUCKET_NAME)
            .replace("VIDEO_JOB_ID", video_job.job_id)
            .replace("TRANSCODE_PREFIX", settings.VIDEO_S3_TRANSCODE_PREFIX)
            .replace("SHORT_ID", video.website.short_id)
            .replace("DRIVE_FILE_ID", video_group.drive_file.file_id)
        )
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 200
    video.refresh_from_db()
    video_job.refresh_from_db()
    assert video.videofiles.count() == 3
    assert video.videofiles.filter(destination=DESTINATION_YOUTUBE).count() == 1
    assert video.status == VideoStatus.COMPLETE
    assert video_job.status == data["detail"]["status"]


def test_transcode_jobs_failure(settings, drf_client, video_group):
    """TranscodeJobView should process MediaConvert failure notification appropriately"""
    video = video_group.video
    video_job = video_group.video_job
    with open(f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_error.json", "r") as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", settings.AWS_ACCOUNT_ID)
            .replace("AWS_REGION", settings.AWS_REGION)
            .replace("VIDEO_JOB_ID", video_job.job_id)
        )
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 200
    video.refresh_from_db()
    video_job.refresh_from_db()
    assert video.videofiles.count() == 0
    assert video.status == VideoStatus.FAILED
    assert video_job.status == data["detail"]["status"]


def test_transcode_jobs_wrong_account(drf_client):
    """TranscodeJobView should raise a PermissionDenied if the AWS account id does not match"""
    with open(
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json", "r"
    ) as infile:
        data = json.loads(infile.read().replace("AWS_ACCOUNT_ID", "other_account_id"))
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 403


def test_transcode_jobs_subscribe(settings, mocker, drf_client):
    """TranscodeJobView should confirm a subcsription request"""
    mock_get = mocker.patch("videos.views.requests.get")
    with open(f"{TEST_VIDEOS_WEBHOOK_PATH}/subscribe.json", "r") as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", settings.AWS_ACCOUNT_ID)
            .replace("AWS_REGION", settings.AWS_REGION)
        )
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 200
    mock_get.assert_called_once_with(data["SubscribeURL"])


def test_transcode_jobs_subscribe_denied(settings, mocker, drf_client):
    """TranscodeJobView should deny a subscription request if the account id is wrong"""
    mock_get = mocker.patch("videos.views.requests.get")
    with open(f"{TEST_VIDEOS_WEBHOOK_PATH}/subscribe.json", "r") as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", "other_account")
            .replace("AWS_REGION", settings.AWS_REGION)
        )
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 403
    mock_get.assert_not_called()
