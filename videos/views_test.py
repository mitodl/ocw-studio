"""Tests for videos.views"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.http.response import HttpResponse
from django.urls import reverse

from gdrive_sync.factories import DriveFileFactory
from users.factories import UserFactory
from videos.conftest import TEST_VIDEOS_WEBHOOK_PATH
from videos.constants import DESTINATION_YOUTUBE, VideoJobStatus, VideoStatus
from videos.factories import VideoFactory, VideoJobFactory
from websites.factories import WebsiteFactory

# pylint:disable=redefined-outer-name
pytestmark = pytest.mark.django_db


@pytest.fixture()
def video_group(settings):
    """Collection of model objects for testing video views"""  # noqa: D401
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
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json",
        encoding="utf-8",
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
    assert video_job.status == VideoJobStatus.COMPLETE


def test_transcode_jobs_failure(settings, drf_client, video_group):
    """TranscodeJobView should process MediaConvert failure notification appropriately"""
    video = video_group.video
    video_job = video_group.video_job
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_error.json", encoding="utf-8"
    ) as infile:
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
    assert video_job.status == VideoJobStatus.FAILED


def test_transcode_jobs_wrong_account(drf_client):
    """TranscodeJobView should raise a PermissionDenied if the AWS account id does not match"""
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/cloudwatch_sns_complete.json",
        encoding="utf-8",
    ) as infile:
        data = json.loads(infile.read().replace("AWS_ACCOUNT_ID", "other_account_id"))
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 403


def test_transcode_jobs_subscribe(settings, mocker, drf_client):
    """TranscodeJobView should confirm a subcsription request"""
    mock_get = mocker.patch("videos.views.requests.get")
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/subscribe.json", encoding="utf-8"
    ) as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", settings.AWS_ACCOUNT_ID)
            .replace("AWS_REGION", settings.AWS_REGION)
        )
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 200
    mock_get.assert_called_once_with(data["SubscribeURL"], timeout=60)


def test_transcode_jobs_subscribe_denied(settings, mocker, drf_client):
    """TranscodeJobView should deny a subscription request if the account id is wrong"""
    mock_get = mocker.patch("videos.views.requests.get")
    with open(  # noqa: PTH123
        f"{TEST_VIDEOS_WEBHOOK_PATH}/subscribe.json", encoding="utf-8"
    ) as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", "other_account")
            .replace("AWS_REGION", settings.AWS_REGION)
        )
    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 403
    mock_get.assert_not_called()


def test_transcode_jobs_subscribe_bad_request(settings, mocker, drf_client):
    """TranscodeJobView should deny a subscription request if token is invalid"""
    mock_get = mocker.patch("videos.views.requests.get")
    with Path(f"{TEST_VIDEOS_WEBHOOK_PATH}/subscribe.json").open(
        encoding="utf-8"
    ) as infile:
        data = json.loads(
            infile.read()
            .replace("AWS_ACCOUNT_ID", settings.AWS_ACCOUNT_ID)
            .replace("AWS_REGION", settings.AWS_REGION)
        )

    # mock token
    data["Token"] = ""

    response = drf_client.post(reverse("transcode_jobs"), data=data)
    assert response.status_code == 400
    mock_get.assert_not_called()


@pytest.mark.parametrize("callback_key", [None, "callback_key", "different_key"])
@pytest.mark.parametrize("video_status", ["submitted_for_transcription", "complete"])
def test_transcript_job(mocker, video_status, callback_key, drf_client, settings):
    """TranscriptJobView should confirm a request and start update_transcripts_for_video job"""
    settings.THREEPLAY_CALLBACK_KEY = "callback_key"

    video = VideoFactory.create(status=video_status)
    update_transcripts_for_video_call = mocker.patch(
        "videos.views.update_transcripts_for_video.delay"
    )

    if callback_key:
        response = drf_client.post(
            reverse("transcript_jobs")
            + "?video_id="
            + str(video.id)
            + "&callback_key="
            + callback_key
        )
    else:
        response = drf_client.post(
            reverse("transcript_jobs") + "?video_id=" + str(video.id)
        )

    assert response.status_code == 200

    if video_status == "submitted_for_transcription" and (
        callback_key == "callback_key"
    ):
        update_transcripts_for_video_call.assert_called_once_with(video.id)
    else:
        update_transcripts_for_video_call.assert_not_called()


def test_youtube_token_initial_get(mocker, admin_client):
    """User should be redirected to an authentication url"""
    mock_redirect = mocker.patch("videos.views.redirect", return_value=HttpResponse())
    mocker.patch("rest_framework.views.isinstance", return_value=True)
    admin_client.get(reverse("yt_tokens"), follow=True)
    mock_redirect.assert_called_once()


def test_youtube_token_callback(mocker, admin_client):
    """User should receive access and refresh tokens"""
    mock_flow = mocker.patch(
        "videos.views.InstalledAppFlow.from_client_config",
        return_value=mocker.Mock(
            credentials=mocker.Mock(token="a", refresh_token="b")  # noqa: S106
        ),
    )
    response = admin_client.get(f"{reverse('yt_tokens')}?code=abcdef")
    mock_flow.return_value.fetch_token.assert_called_once()
    assert response.json() == {"YT_ACCESS_TOKEN": "a", "YT_REFRESH_TOKEN": "b"}


def test_youtube_token_admins_only(drf_client):
    """A non-admin user should get a 403"""
    drf_client.force_login(UserFactory.create())
    response = drf_client.get(reverse("yt_tokens"), follow=True)
    assert response.status_code == 403
