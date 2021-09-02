""" videos.tasks tests"""
import string
from random import choice

import boto3
import pytest
from django.conf import settings
from googleapiclient.errors import HttpError, ResumableUploadError
from moto import mock_s3

from ocw_import.conftest import MOCK_BUCKET_NAME, setup_s3
from videos.conftest import MockHttpErrorResponse
from videos.constants import (
    DESTINATION_YOUTUBE,
    VideoFileStatus,
    VideoStatus,
    YouTubeStatus,
)
from videos.factories import VideoFileFactory
from videos.models import VideoFile
from videos.tasks import (
    delete_s3_objects,
    remove_youtube_video,
    update_youtube_statuses,
    upload_youtube_videos,
)
from videos.youtube import API_QUOTA_ERROR_MSG


# pylint:disable=unused-argument,redefined-outer-name
pytestmark = pytest.mark.django_db


@pytest.fixture
def youtube_video_files_new():
    """Return 3 Youtube video files"""
    return VideoFileFactory.create_batch(
        3,
        status=VideoStatus.CREATED,
        destination=DESTINATION_YOUTUBE,
        destination_id=None,
    )


@pytest.fixture
def youtube_video_files_processing():
    """Return 3 Youtube video files"""
    return VideoFileFactory.create_batch(
        3,
        status=VideoFileStatus.UPLOADED,
        destination=DESTINATION_YOUTUBE,
        destination_status=YouTubeStatus.PROCESSING,
    )


@pytest.mark.parametrize("is_enabled", [True, False])
@pytest.mark.parametrize("max_uploads", [2, 4])
def test_upload_youtube_videos(
    mocker, youtube_video_files_new, max_uploads, is_enabled
):
    """
    Test that the upload_youtube_videos task calls YouTubeApi.upload_video
    & creates a YoutubeVideo object for each public video, up to the max daily limit
    """
    if not is_enabled:
        settings.YT_CLIENT_ID = None
    settings.YT_UPLOAD_LIMIT = max_uploads
    mock_uploader = mocker.patch(
        "videos.tasks.YouTubeApi.upload_video",
        return_value={
            "id": "".join([choice(string.ascii_lowercase) for n in range(8)]),
            "status": {"uploadStatus": "uploaded"},
        },
    )
    upload_youtube_videos()
    assert mock_uploader.call_count == (min(3, max_uploads) if is_enabled else 0)
    if is_enabled:
        for video_file in VideoFile.objects.order_by("-created_on")[
            : settings.YT_UPLOAD_LIMIT
        ]:
            assert video_file.destination_id is not None
            assert video_file.destination_status == YouTubeStatus.UPLOADED
            assert video_file.status == VideoFileStatus.UPLOADED


def test_upload_youtube_videos_error(mocker, youtube_video_files_new):
    """
    Test that the VideoFile status is set properly if an error occurs during upload, and all videos are processed
    """
    mock_uploader = mocker.patch(
        "videos.tasks.YouTubeApi.upload_video", side_effect=OSError
    )
    upload_youtube_videos()
    assert mock_uploader.call_count == 3
    for video_file in youtube_video_files_new:
        video_file.refresh_from_db()
        assert video_file.status == VideoFileStatus.FAILED


@pytest.mark.parametrize(
    "msg,status",
    [
        [API_QUOTA_ERROR_MSG, VideoFileStatus.CREATED],
        ["other error", VideoFileStatus.FAILED],
    ],
)
def test_upload_youtube_quota_exceeded(mocker, youtube_video_files_new, msg, status):
    """
    Test that the YoutubeVideo object is deleted if an error occurs during upload,
    and the loop is halted if the quota is exceeded.
    """
    mock_uploader = mocker.patch(
        "videos.tasks.YouTubeApi.upload_video",
        side_effect=ResumableUploadError(
            MockHttpErrorResponse(403), str.encode(msg, "utf-8")
        ),
    )
    upload_youtube_videos()
    assert mock_uploader.call_count == (1 if msg == API_QUOTA_ERROR_MSG else 3)
    for video_file in youtube_video_files_new:
        video_file.refresh_from_db()
        assert video_file.status == status
        assert video_file.destination_status is None
        assert video_file.destination_id is None


@pytest.mark.parametrize("is_enabled", [True, False])
def test_update_youtube_statuses(
    settings,
    mocker,
    youtube_video_files_processing,
    youtube_video_files_new,
    is_enabled,
):
    """
    Test that the correct number of YouTubeVideo objects have their statuses updated to the correct value.
    """
    if not is_enabled:
        settings.YT_CLIENT_ID = None
    mocker.patch(
        "videos.tasks.YouTubeApi.video_status", return_value=YouTubeStatus.PROCESSED
    )
    update_youtube_statuses()
    assert VideoFile.objects.filter(
        destination_status=YouTubeStatus.PROCESSED, status=VideoFileStatus.COMPLETE
    ).count() == (3 if is_enabled else 0)


def test_update_youtube_statuses_api_quota_exceeded(
    mocker, youtube_video_files_processing
):
    """
    Test that the update_youtube_statuses task stops without raising an error if the API quota is exceeded.
    """
    mock_video_status = mocker.patch(
        "videos.tasks.YouTubeApi.video_status",
        side_effect=HttpError(
            MockHttpErrorResponse(403), str.encode(API_QUOTA_ERROR_MSG, "utf-8")
        ),
    )
    update_youtube_statuses()
    mock_video_status.assert_called_once()


def test_update_youtube_statuses_http_error(mocker, youtube_video_files_processing):
    """
    Test that an error is raised if any http error occurs other than exceeding daily API quota
    """
    mock_video_status = mocker.patch(
        "videos.tasks.YouTubeApi.video_status",
        side_effect=HttpError(MockHttpErrorResponse(403), b"other error"),
    )
    with pytest.raises(HttpError):
        update_youtube_statuses()
    mock_video_status.assert_called_once()


def test_update_youtube_statuses_index_error(mocker, youtube_video_files_processing):
    """
    Test that an error is raised if a index error occurs
    """
    mock_log = mocker.patch("videos.tasks.log.exception")
    mocker.patch(
        "videos.tasks.YouTubeApi.video_status",
        side_effect=IndexError(),
    )
    update_youtube_statuses()
    for video_file in youtube_video_files_processing:
        mock_log.assert_any_call(
            "Status of YoutubeVideo not found: s3_key %s, youtube_id %s",
            video_file.s3_key,
            video_file.destination_id,
        )


@pytest.mark.parametrize("is_enabled", [True, False])
def test_remove_youtube_video(
    settings, mocker, youtube_video_files_processing, is_enabled
):
    """Verify that remove_youtube_video makes the appropriate api call to delete a video"""
    if not is_enabled:
        settings.YT_CLIENT_ID = None
    mock_delete = mocker.patch("videos.tasks.YouTubeApi.delete_video")
    video_file = youtube_video_files_processing[0]
    remove_youtube_video(video_file.destination_id)
    if is_enabled:
        mock_delete.assert_called_once_with(video_file.destination_id)
    else:
        mock_delete.assert_not_called()


def test_remove_youtube_video_404_error(mocker, youtube_video_files_processing):
    """Test that a 404 http error is handled appropriately and logged"""
    mock_log = mocker.patch("videos.tasks.log.info")
    mocker.patch(
        "videos.tasks.YouTubeApi.delete_video",
        side_effect=HttpError(MockHttpErrorResponse(404), b"error"),
    )
    video_file = youtube_video_files_processing[0]
    remove_youtube_video(video_file.destination_id)
    mock_log.assert_called_once_with(
        "Not found on Youtube, already deleted?", video_id=video_file.destination_id
    )


def test_remove_youtube_video_other_http_error(mocker, youtube_video_files_processing):
    """Test that a non-404 http error is raised"""
    mocker.patch(
        "videos.tasks.YouTubeApi.delete_video",
        side_effect=HttpError(MockHttpErrorResponse(500), b"error"),
    )
    video_file = youtube_video_files_processing[0]
    with pytest.raises(HttpError):
        remove_youtube_video(video_file.destination_id)


@mock_s3
def test_delete_s3_objects(settings):
    """Test that s3 objects are deleted"""
    settings.AWS_STORAGE_BUCKET_NAME = MOCK_BUCKET_NAME
    setup_s3(settings)
    client = boto3.client("s3")
    assert (
        client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/config/_default/menus.yaml"
        )
        is not None
    )
    assert (
        client.get_object(Bucket=MOCK_BUCKET_NAME, Key="biology/content/_index.md")
        is not None
    )
    delete_s3_objects(key="biology/config/_default/menus.yaml")
    with pytest.raises(client.exceptions.NoSuchKey):
        assert client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/config/_default/menus.yaml"
        )
    assert (
        client.get_object(Bucket=MOCK_BUCKET_NAME, Key="biology/content/_index.md")
        is not None
    )
    delete_s3_objects(key="biology/content")
    assert (
        client.get_object(Bucket=MOCK_BUCKET_NAME, Key="biology/content/_index.md")
        is not None
    )
    delete_s3_objects(key="biology/content", as_filter=True)
    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(Bucket=MOCK_BUCKET_NAME, Key="biology/content/_index.md")
