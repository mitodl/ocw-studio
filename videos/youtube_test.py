"""
Tests for youtube api
"""
import random
import string

import pytest
from googleapiclient.errors import HttpError

from videos.conftest import MockHttpErrorResponse
from videos.factories import VideoFileFactory
from videos.youtube import YouTubeApi, YouTubeUploadException, strip_bad_chars


pytestmark = pytest.mark.django_db

# pylint: disable=redefined-outer-name,unused-argument,no-value-for-parameter,unused-variable


def test_youtube_settings(mocker, settings):
    """
    Test that Youtube object creation uses YT_* settings for credentials
    """
    settings.YT_ACCESS_TOKEN = "yt_access_token"
    settings.YT_CLIENT_ID = "yt_client_id"
    settings.YT_CLIENT_SECRET = "yt_secret"
    settings.YT_REFRESH_TOKEN = "yt_refresh"
    mock_oauth = mocker.patch("videos.youtube.oauth2client.client.GoogleCredentials")
    YouTubeApi()
    mock_oauth.assert_called_with(
        settings.YT_ACCESS_TOKEN,
        settings.YT_CLIENT_ID,
        settings.YT_CLIENT_SECRET,
        settings.YT_REFRESH_TOKEN,
        None,
        "https://accounts.google.com/o/oauth2/token",
        None,
    )


def test_upload_video(mocker):
    """
    Test that the upload_video task calls the YouTube API execute method
    """
    videofile = VideoFileFactory()
    youtube_id = "M6LymW_8qVk"
    video_upload_response = {
        "id": youtube_id,
        "kind": "youtube#video",
        "snippet": {"description": "Testing description", "title": "Testing123"},
        "status": {"uploadStatus": "uploaded"},
    }
    youtube_mocker = mocker.patch("videos.youtube.build")
    youtube_mocker().videos.return_value.insert.return_value.next_chunk.side_effect = [
        (None, None),
        (None, video_upload_response),
    ]
    response = YouTubeApi().upload_video(videofile)
    assert response == video_upload_response


def test_upload_video_no_id(mocker):
    """
    Test that the upload_video task fails if the response contains no id
    """
    videofile = VideoFileFactory()
    youtube_mocker = mocker.patch("videos.youtube.build")
    youtube_mocker().videos.return_value.insert.return_value.next_chunk.return_value = (
        None,
        {},
    )
    with pytest.raises(YouTubeUploadException):
        YouTubeApi().upload_video(videofile)


@pytest.mark.parametrize(
    ["error", "retryable"],
    [
        [HttpError(MockHttpErrorResponse(500), b""), True],
        [HttpError(MockHttpErrorResponse(403), b""), False],
        [OSError, True],
        [IndexError, False],
    ],
)
def test_upload_errors_retryable(mocker, error, retryable):
    """
    Test that uploads are retried 10x for retryable exceptions
    """
    youtube_mocker = mocker.patch("videos.youtube.build")
    mocker.patch("videos.youtube.time")
    videofile = VideoFileFactory()
    youtube_mocker().videos.return_value.insert.return_value.next_chunk.side_effect = (
        error
    )
    with pytest.raises(Exception) as exc:
        YouTubeApi().upload_video(videofile)
    assert str(exc.value).startswith("Retried YouTube upload 10x") == retryable


def test_upload_video_long_fields(mocker):
    """
    Test that the upload_youtube_video task truncates title and description if too long
    """
    name = "".join(random.choice(string.ascii_lowercase) for c in range(105))
    video_file = VideoFileFactory.create()
    video_file.video.source_key = video_file.s3_key.replace("file_", name)
    mocker.patch("videos.youtube.resumable_upload")
    youtube_mocker = mocker.patch("videos.youtube.build")
    mock_upload = youtube_mocker().videos.return_value.insert
    YouTubeApi().upload_video(video_file)
    called_args, called_kwargs = mock_upload.call_args
    assert called_kwargs["body"]["snippet"]["title"] == name[:100]


def test_delete_video(mocker):
    """
    Test that the 'delete_video' method executes a YouTube API deletion request and returns the status code
    """
    youtube_mocker = mocker.patch("videos.youtube.build")
    youtube_mocker().videos.return_value.delete.return_value.execute.return_value = 204
    assert YouTubeApi().delete_video("foo") == 204
    youtube_mocker().videos.return_value.delete.assert_called_with(id="foo")


def test_video_status(mocker):
    """
    Test that the 'video_status' method returns the correct value from the API response
    """
    expected_status = "processed"
    youtube_mocker = mocker.patch("videos.youtube.build")
    youtube_mocker().videos.return_value.list.return_value.execute.return_value = {
        "etag": '"ld9biNPKjAjgjV7EZ4EKeEGrhao/Lf7oS5V-Gjw0XHBBKFJRpn60z3w"',
        "items": [
            {
                "etag": '"ld9biNPKjAjgjV7EZ4EKeEGrhao/-UL82wRXbq3YJiMZuZpqCWKoq6Q"',
                "id": "wAjoqsZng_M",
                "kind": "youtube#video",
                "status": {
                    "embeddable": True,
                    "license": "youtube",
                    "privacyStatus": "unlisted",
                    "publicStatsViewable": True,
                    "uploadStatus": expected_status,
                },
            }
        ],
        "kind": "youtube#videoListResponse",
        "pageInfo": {"resultsPerPage": 1, "totalResults": 1},
    }
    assert YouTubeApi().video_status("foo") == expected_status
    youtube_mocker().videos.return_value.list.assert_called_once_with(
        id="foo", part="status"
    )


def test_strip_bad_chars():
    """
    Test that `<`,`>` characters are removed from text
    """
    assert strip_bad_chars("<OV>S>") == "OVS"
