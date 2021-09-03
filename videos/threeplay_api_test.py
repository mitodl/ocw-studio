"""tests for 3play api requests"""

from io import BytesIO

import pytest

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from videos.threeplay_api import (
    fetch_file,
    threeplay_remove_tags,
    threeplay_transcript_api_request,
    threeplay_updated_media_file_request,
    update_transcripts_for_video,
    update_transcripts_for_website,
)
from websites.factories import WebsiteFactory
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
def test_update_transcripts_for_video(
    mocker, settings, pdf_transcript_content, webvtt_transcript_content
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
        "data": [
            {
                "id": 2,
                "media_file_id": 3,
            }
        ],
    }

    mocker.patch(
        "videos.threeplay_api.threeplay_transcript_api_request",
        return_value=threeplay_response,
    )

    mock_fetch_file = mocker.patch("videos.threeplay_api.fetch_file")
    mock_fetch_file.side_effect = [pdf_transcript_content, webvtt_transcript_content]

    update_transcripts_for_video(video)

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

    if pdf_transcript_content:
        assert video_file.video.pdf_transcript_file.path.startswith(
            url_base + "_transcript"
        )
        assert video_file.video.pdf_transcript_file.path.endswith(".pdf")
    else:
        assert video_file.video.pdf_transcript_file == ""

    if webvtt_transcript_content:
        assert video_file.video.webvtt_transcript_file.path.startswith(
            url_base + "_transcript_webvtt"
        )
    else:
        assert video_file.video.webvtt_transcript_file == ""


def test_update_transcripts_for_website(mocker):
    """test update_transcripts_for_website"""
    website = WebsiteFactory.create()
    videos = VideoFactory.create_batch(4, website=website)
    update_video_transcript = mocker.patch(
        "videos.threeplay_api.update_transcripts_for_video"
    )

    update_transcripts_for_website(website)

    for video in videos:
        update_video_transcript.assert_any_call(video)
