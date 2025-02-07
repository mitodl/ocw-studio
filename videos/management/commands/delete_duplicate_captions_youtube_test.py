"""
Tests for the delete_duplicate_captions_youtube management command.

Verifies that the command inspects YouTube caption tracks for each VideoFile and handles
'ocw_studio_upload' vs. 'CC (English)' as expected.
"""

import pytest
from django.core.management import call_command

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from videos.youtube import CAPTION_UPLOAD_NAME
from websites.factories import WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture()
def mock_youtube_api(mocker):
    """Mock the YouTube API client"""
    mocker.resetall()
    mock_api_cls = mocker.patch("videos.youtube.YouTubeApi")
    mock_api = mock_api_cls.return_value
    mock_api.client.captions.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "caption_id_legacy",
                "snippet": {
                    "name": "ocw_studio_upload",
                    "lastUpdated": "2023-10-01T12:00:00.000Z",
                },
            },
            {
                "id": "caption_id_other",
                "snippet": {
                    "name": CAPTION_UPLOAD_NAME,
                    "lastUpdated": "2023-09-30T12:00:00.000Z",
                },
            },
        ]
    }
    mock_api.client.captions.return_value.download.return_value.execute.return_value = (
        b"some vtt data"
    )
    return mock_api


def test_delete_duplicate_captions_youtube_command(mock_youtube_api):
    """
    Tests that the command finds VideoFile objects, checks if the newest
    caption name is 'ocw_studio_upload', and copies it to 'CC (English)' before deleting it.
    """
    website = WebsiteFactory.create(name="Test Site", short_id="test-site")

    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="dummy_youtube_id",
    )

    call_command("delete_duplicate_captions_youtube", filter="test-site")

    mock_youtube_api.client.captions.return_value.list.assert_called_with(
        part="snippet", videoId="dummy_youtube_id"
    )
    mock_youtube_api.client.captions.return_value.download.assert_called_once()

    mock_youtube_api.client.captions.return_value.delete.assert_called_once_with(
        id="caption_id_legacy"
    )


@pytest.fixture()
def mock_youtube_api_cc_english_newest(mocker):
    """
    Alternate fixture: newest track is 'CC (English)'
    and older track is 'ocw_studio_upload'.
    """
    mock_api_cls = mocker.patch("videos.youtube.YouTubeApi")
    mock_api = mock_api_cls.return_value

    mock_api.client.captions.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "caption_id_legacy",
                "snippet": {
                    "name": "ocw_studio_upload",
                    "lastUpdated": "2023-09-30T12:00:00.000Z",
                },
            },
            {
                "id": "caption_id_other",
                "snippet": {
                    "name": CAPTION_UPLOAD_NAME,
                    "lastUpdated": "2023-10-01T12:00:00.000Z",
                },
            },
        ]
    }
    mock_api.client.captions.return_value.download.return_value.execute.return_value = (
        b"some vtt data"
    )
    return mock_api


def test_delete_duplicate_captions_youtube_command_cc_english_newest(
    mock_youtube_api_cc_english_newest,
):
    """
    If 'ocw_studio_upload' is not the newest track, we do not download/update it
    to the 'CC (English)' track. Instead, if the newest is 'CC (English)' and there
    is a legacy track, we delete the legacy track without copying from it.
    """
    website = WebsiteFactory.create(name="Test Site", short_id="test-site")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="dummy_youtube_id",
    )

    call_command("delete_duplicate_captions_youtube", filter="test-site")

    mock_youtube_api_cc_english_newest.client.captions.return_value.list.assert_called_with(
        part="snippet", videoId="dummy_youtube_id"
    )
    mock_youtube_api_cc_english_newest.client.captions.return_value.download.assert_not_called()
    mock_youtube_api_cc_english_newest.client.captions.return_value.update.assert_not_called()
    mock_youtube_api_cc_english_newest.client.captions.return_value.insert.assert_not_called()
    mock_youtube_api_cc_english_newest.client.captions.return_value.delete.assert_called_once_with(
        id="caption_id_legacy"
    )
