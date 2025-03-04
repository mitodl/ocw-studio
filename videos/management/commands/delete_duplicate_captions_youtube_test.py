"""
Tests for the delete_duplicate_captions_youtube management command.

Verifies that the command:
- Properly inspects YouTube caption tracks for each VideoFile
- Handles 'ocw_captions_upload' vs. 'CC (English)' tracks appropriately:
  - Copies content from 'ocw_captions_upload' to 'CC (English)' when the former is newer
  - Only deletes 'ocw_captions_upload' when 'CC (English)' is newer
- Ignores auto-generated caption tracks in any language
- Takes no action when only auto-generated captions exist
"""

import pytest
from django.core.management import call_command

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from videos.management.commands.delete_duplicate_captions_youtube import (
    LEGACY_CAPTIONS_NAME,
)
from videos.youtube import CAPTION_UPLOAD_NAME
from websites.factories import WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture()
def mock_youtube_api(mocker):
    """Mock the YouTube API client"""
    mock_api_cls = mocker.patch(
        "videos.management.commands.delete_duplicate_captions_youtube.YouTubeApi"
    )
    mock_api = mock_api_cls.return_value
    mock_api.client.captions.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "caption_id_legacy",
                "snippet": {
                    "name": LEGACY_CAPTIONS_NAME,
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
    caption name is 'ocw_captions_upload', and copies it to 'CC (English)' before deleting it.
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
    and older track is 'ocw_captions_upload'.
    """
    mock_api_cls = mocker.patch(
        "videos.management.commands.delete_duplicate_captions_youtube.YouTubeApi"
    )
    mock_api = mock_api_cls.return_value

    mock_api.client.captions.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "caption_id_legacy",
                "snippet": {
                    "name": LEGACY_CAPTIONS_NAME,
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
    If 'ocw_captions_upload' is not the newest track, we do not download/update it
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


@pytest.fixture()
def mock_youtube_api_with_auto_captions(mocker):
    """
    Fixture with our managed caption tracks plus auto-generated captions in other languages.
    """
    mock_api_cls = mocker.patch(
        "videos.management.commands.delete_duplicate_captions_youtube.YouTubeApi"
    )
    mock_api = mock_api_cls.return_value

    mock_api.client.captions.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "auto_ru_caption",
                "snippet": {
                    "videoId": "dummy_youtube_id",
                    "lastUpdated": "2023-10-02T12:00:00.000Z",
                    "trackKind": "asr",
                    "language": "ru",
                    "name": "",
                    "audioTracktype": "unknown",
                    "isCC": False,
                },
            },
            {
                "id": "caption_id_legacy",
                "snippet": {
                    "name": LEGACY_CAPTIONS_NAME,
                    "lastUpdated": "2023-09-30T12:00:00.000Z",
                    "language": "en",
                },
            },
            {
                "id": "caption_id_other",
                "snippet": {
                    "name": CAPTION_UPLOAD_NAME,
                    "lastUpdated": "2023-10-01T12:00:00.000Z",
                    "language": "en",
                },
            },
            {
                "id": "auto_es_caption",
                "snippet": {
                    "videoId": "dummy_youtube_id",
                    "lastUpdated": "2023-10-02T13:00:00.000Z",
                    "trackKind": "asr",
                    "language": "es",
                    "name": "",
                    "audioTracktype": "unknown",
                    "isCC": False,
                },
            },
        ]
    }
    mock_api.client.captions.return_value.download.return_value.execute.return_value = (
        b"some vtt data"
    )
    return mock_api


def test_delete_duplicate_captions_with_auto_captions(
    mock_youtube_api_with_auto_captions,
):
    """
    Test that managed caption tracks are correctly handled and auto-generated
    captions in other languages are ignored, even if they are newer.
    """
    website = WebsiteFactory.create(name="Test Site", short_id="test-site-auto")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="dummy_youtube_id",
    )

    call_command("delete_duplicate_captions_youtube", filter="test-site-auto")

    mock_youtube_api_with_auto_captions.client.captions.return_value.list.assert_called_with(
        part="snippet", videoId="dummy_youtube_id"
    )
    mock_youtube_api_with_auto_captions.client.captions.return_value.download.assert_not_called()

    mock_youtube_api_with_auto_captions.client.captions.return_value.delete.assert_called_once_with(
        id="caption_id_legacy"
    )

    assert "auto_ru_caption" not in str(
        mock_youtube_api_with_auto_captions.client.captions.return_value.delete.call_args_list
    )
    assert "auto_es_caption" not in str(
        mock_youtube_api_with_auto_captions.client.captions.return_value.delete.call_args_list
    )


@pytest.fixture()
def mock_youtube_api_only_auto_captions(mocker):
    """
    Fixture with only auto-generated captions, no managed tracks.
    """
    mock_api_cls = mocker.patch(
        "videos.management.commands.delete_duplicate_captions_youtube.YouTubeApi"
    )
    mock_api = mock_api_cls.return_value

    mock_api.client.captions.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "auto_ru_caption",
                "snippet": {
                    "videoId": "dummy_youtube_id",
                    "lastUpdated": "2023-10-02T12:00:00.000Z",
                    "trackKind": "asr",
                    "language": "ru",
                    "name": "",
                    "audioTracktype": "unknown",
                    "isCC": False,
                },
            },
            {
                "id": "auto_en_caption",
                "snippet": {
                    "videoId": "dummy_youtube_id",
                    "lastUpdated": "2023-10-02T13:00:00.000Z",
                    "trackKind": "asr",
                    "language": "en",
                    "name": "",
                    "audioTracktype": "unknown",
                    "isCC": False,
                },
            },
        ]
    }
    return mock_api


def test_with_only_auto_captions(
    mock_youtube_api_only_auto_captions,
):
    """
    Tests that nothing is done when there are only auto-generated captions and none
    of the managed caption tracks.
    """
    website = WebsiteFactory.create(name="Test Site", short_id="test-site-auto-only")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="dummy_youtube_id",
    )

    call_command("delete_duplicate_captions_youtube", filter="test-site-auto-only")

    mock_youtube_api_only_auto_captions.client.captions.return_value.list.assert_called_with(
        part="snippet", videoId="dummy_youtube_id"
    )

    mock_youtube_api_only_auto_captions.client.captions.return_value.download.assert_not_called()
    mock_youtube_api_only_auto_captions.client.captions.return_value.insert.assert_not_called()
    mock_youtube_api_only_auto_captions.client.captions.return_value.update.assert_not_called()
    mock_youtube_api_only_auto_captions.client.captions.return_value.delete.assert_not_called()
