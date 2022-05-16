"""tests for 3play api requests"""

from io import BytesIO

import pytest

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFileFactory
from videos.threeplay_api import (
    create_folder,
    fetch_file,
    get_folder,
    get_or_create_folder,
    threeplay_order_transcript_request,
    threeplay_remove_tags,
    threeplay_transcript_api_request,
    threeplay_updated_media_file_request,
    threeplay_upload_video_request,
    update_transcripts_for_video,
)
from websites.site_config_api import SiteConfig


pytestmark = pytest.mark.django_db


def test_threeplay_updated_media_file_request(mocker, settings):
    """test threeplay_updated_media_file_request"""

    settings.THREEPLAY_API_KEY = "key"
    mock_get_call = mocker.patch("videos.threeplay_api.requests.get")

    threeplay_updated_media_file_request()

    mock_get_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/files", {"label": "updated", "api_key": "key"}
    )


def test_threeplay_remove_tags(mocker, settings):
    """test threeplay_remove_tags"""

    settings.THREEPLAY_API_KEY = "key"
    mock_patch_call = mocker.patch("videos.threeplay_api.requests.patch")

    threeplay_remove_tags(12345)

    mock_patch_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/files/12345", {"label": "", "api_key": "key"}
    )


def test_threeplay_transcript_api_request(mocker, settings):
    """test threeplay_transcript_api_request"""

    settings.THREEPLAY_API_KEY = "key"
    mock_get_call = mocker.patch("videos.threeplay_api.requests.get")

    threeplay_transcript_api_request("youtube_id")

    mock_get_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/transcripts",
        {"media_file_reference_id": "youtube_id", "api_key": "key"},
    )


@pytest.mark.parametrize(
    "status_code,content",
    [
        (200, b"content"),
        (200, b'{"is_error":true,"error_description":"record not found"}'),
        (500, b"content"),
    ],
)
def test_fetch_file(mocker, content, status_code):
    """test fetch_file"""
    request_call = mocker.patch("videos.threeplay_api.requests.get")
    request_call.return_value.content = content
    request_call.return_value.status_code = status_code

    result = fetch_file("source_url.com")

    if status_code == 200 and content == b"content":
        assert result.getvalue() == content
    else:
        assert not result


@pytest.mark.parametrize("pdf_transcript_content", [False, BytesIO(b"content")])
@pytest.mark.parametrize("webvtt_transcript_content", [False, BytesIO(b"content")])
@pytest.mark.parametrize("status", ["complete", "in_progress"])
def test_update_transcripts_for_video(
    mocker, settings, pdf_transcript_content, webvtt_transcript_content, status
):
    """test update_transcripts_for_video"""

    settings.THREEPLAY_PROJECT_ID = 1

    video_file = VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, destination_id="123"
    )
    video = video_file.video
    video.pdf_transcript_file = ""
    video.webvtt_transcript_file = ""
    video.save()

    threeplay_response = {
        "code": 200,
        "data": [{"id": 2, "media_file_id": 3, "status": status}],
    }

    mocker.patch(
        "videos.threeplay_api.threeplay_transcript_api_request",
        return_value=threeplay_response,
    )

    mock_fetch_file = mocker.patch("videos.threeplay_api.fetch_file")
    mock_fetch_file.side_effect = [pdf_transcript_content, webvtt_transcript_content]

    update_transcripts_for_video(video)

    if status == "complete":
        mock_fetch_file.assert_any_call(
            "https://static.3playmedia.com/p/files/3/threeplay_transcripts/2?project_id=1&format_id=51"
        )

        mock_fetch_file.assert_any_call(
            "https://static.3playmedia.com/p/files/3/threeplay_transcripts/2?project_id=1&format_id=46"
        )

    site_config = SiteConfig(video.website.starter.config)
    url_base = "/".join(
        [
            settings.MEDIA_ROOT.rstrip("/"),
            site_config.root_url_path,
            video.website.name,
            video.source_key.split("/")[-2],
        ]
    )

    if pdf_transcript_content and status == "complete":
        assert video_file.video.pdf_transcript_file.path.startswith(
            url_base + "_transcript"
        )
        assert video_file.video.pdf_transcript_file.path.endswith(".pdf")
    else:
        assert video_file.video.pdf_transcript_file == ""

    if webvtt_transcript_content and status == "complete":
        assert video_file.video.webvtt_transcript_file.path.startswith(
            url_base + "_transcript"
        )
        assert video_file.video.webvtt_transcript_file.path.endswith(".webvtt")

    else:
        assert video_file.video.webvtt_transcript_file == ""


def test_get_folder_request(mocker, settings):
    """test get_folder"""
    settings.THREEPLAY_API_KEY = "key"
    mock_get_call = mocker.patch("videos.threeplay_api.requests.get")

    response = get_folder("short_id")

    mock_get_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/batches/", {"name": "short_id", "api_key": "key"}
    )
    assert response == mock_get_call.return_value.json()


def test_create_folder_request(mocker, settings):
    """test create_folder"""
    settings.THREEPLAY_API_KEY = "key"
    mock_post_call = mocker.patch("videos.threeplay_api.requests.post")

    response = create_folder("short_id")

    mock_post_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/batches/", {"name": "short_id", "api_key": "key"}
    )
    assert response == mock_post_call.return_value.json()


@pytest.mark.parametrize(
    "get_folder_response", [{}, {"data": []}, {"data": [{"id": 1}]}]
)
def test_get_or_create_folder(mocker, settings, get_folder_response):
    """test get_or_create_folder"""

    settings.THREEPLAY_API_KEY = "key"

    mock_get_call = mocker.patch("videos.threeplay_api.requests.get")
    mock_post_call = mocker.patch("videos.threeplay_api.requests.post")

    mock_get_call.return_value.json.return_value = get_folder_response
    mock_post_call.return_value.json.return_value = {"data": {"id": 2}}

    response = get_or_create_folder("name")

    if get_folder_response == {"data": [{"id": 1}]}:
        mock_post_call.assert_not_called()

        assert response == 1
    else:
        mock_post_call.assert_called_once_with(
            "https://api.3playmedia.com/v3/batches/", {"name": "name", "api_key": "key"}
        )
        assert response == 2


def test_threeplay_upload_video_request(mocker, settings):
    """test threeplay_upload_video_request"""

    settings.THREEPLAY_API_KEY = "key"
    mocker.patch("videos.threeplay_api.get_or_create_folder", return_value=123)
    mock_post_call = mocker.patch("videos.threeplay_api.requests.post")

    payload = {
        "source_url": "https://www.youtube.com/watch?v=youtube_id",
        "reference_id": "youtube_id",
        "api_key": "key",
        "language_id": [1],
        "name": "title",
        "batch_id": 123,
    }

    result = threeplay_upload_video_request("website_short_id", "youtube_id", "title")

    assert result == mock_post_call.return_value.json()
    mock_post_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/files/", payload
    )


@pytest.mark.parametrize("threeplay_callback_key", [None, "threeplay_callback_key"])
def test_threeplay_order_transcript_request(mocker, settings, threeplay_callback_key):
    """test threeplay_order_transcript_request"""

    settings.SITE_BASE_URL = "http://url.edu/"
    settings.THREEPLAY_API_KEY = "key"
    settings.THREEPLAY_CALLBACK_KEY = threeplay_callback_key

    mock_post_call = mocker.patch("videos.threeplay_api.requests.post")

    payload = {
        "turnaround_level_id": 5,
        "media_file_id": 456,
        "api_key": "key",
    }

    if threeplay_callback_key:
        payload[
            "callback"
        ] = "http://url.edu/api/transcription-jobs/?video_id=123&callback_key=threeplay_callback_key"

    result = threeplay_order_transcript_request(123, 456)

    assert result == mock_post_call.return_value.json()
    mock_post_call.assert_called_once_with(
        "https://api.3playmedia.com/v3/transcripts/order/transcription", payload
    )
