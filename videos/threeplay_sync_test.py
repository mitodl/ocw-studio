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
    """3Play sync should create caption/transcript resources and set _resource fields."""
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
    vf = video.metadata["video_files"]
    # _resource.content is a single-item list (array format post-10982)
    transcript_content = vf["video_transcript_resources"]["content"]
    captions_content = vf["video_captions_resources"]["content"]
    assert isinstance(transcript_content, list)
    assert len(transcript_content) == 1
    assert isinstance(captions_content, list)
    assert len(captions_content) == 1
    # referenced_by tracks via file field on the created WebsiteContent objects
    assert set(video.referenced_by.values_list("file", flat=True)) == {
        f"/courses/{website.name}/yt789_transcript.pdf",
        f"/courses/{website.name}/yt789_captions.webvtt",
    }


def test_sync_video_captions_and_transcripts_skips_if_resource_exists(mocker):
    """3Play sync skips captions/transcripts that already have _resource content set."""
    starter = WebsiteStarterFactory.create(slug="ocw-course-v2")
    website = WebsiteFactory.create(starter=starter)
    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {
                "video_captions_resources": {
                    "content": ["some-text-id"],
                    "website": website.name,
                },
                "video_transcript_resources": {
                    "content": ["some-other-id"],
                    "website": website.name,
                },
            },
        },
    )

    mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        return_value={"data": [{"status": "complete", "id": 11, "media_file_id": 22}]},
    )
    fetch_file_mock = mocker.patch("videos.threeplay_sync.fetch_file")

    sync_video_captions_and_transcripts(video)

    fetch_file_mock.assert_not_called()


def test_sync_video_captions_and_transcripts_treats_empty_content_as_unset(mocker):
    """Empty-string _resource.content is treated as unset; 3Play fetch proceeds."""
    starter = WebsiteStarterFactory.create(slug="ocw-course-v2")
    website = WebsiteFactory.create(starter=starter)
    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {
                # Site-config initialises relation widgets with empty content
                "video_captions_resources": {"content": "", "website": ""},
                "video_transcript_resources": {"content": "", "website": ""},
            },
        },
    )

    mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        return_value={"data": [{"status": "complete", "id": 11, "media_file_id": 22}]},
    )
    fetch_file_mock = mocker.patch(
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

    # Both files were fetched (empty content treated as unset)
    assert fetch_file_mock.call_count == 2
    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert isinstance(vf["video_transcript_resources"]["content"], list)
    assert isinstance(vf["video_captions_resources"]["content"], list)
