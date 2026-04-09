"""Tests for videos.threeplay_sync."""

from io import BytesIO

import pytest

from videos.threeplay_sync import sync_video_captions_and_transcripts
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)

pytestmark = pytest.mark.django_db


def test_sync_video_captions_and_transcripts_sets_references(mocker):
    """3Play sync should attach created caption/transcript resources as references."""
    starter = WebsiteStarterFactory.create(slug="ocw-course-v2")
    website = WebsiteFactory.create(starter=starter)
    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {},
        },
    )

    mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        return_value={"data": [{"status": "complete", "id": 11, "media_file_id": 22}]},
    )
    mocker.patch(
        "videos.threeplay_sync.fetch_file",
        side_effect=[BytesIO(b"pdf"), BytesIO(b"webvtt")],
    )
    mocker.patch(
        "videos.threeplay_sync.upload_to_s3",
        side_effect=[
            f"/courses/{website.name}/yt789_transcript.pdf",
            f"/courses/{website.name}/yt789_captions.webvtt",
        ],
    )

    sync_video_captions_and_transcripts(video)

    video.refresh_from_db()
    assert set(video.referenced_by.values_list("file", flat=True)) == {
        f"/courses/{website.name}/yt789_transcript.pdf",
        f"/courses/{website.name}/yt789_captions.webvtt",
    }
