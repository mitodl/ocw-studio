"""Tests for videos.threeplay_sync."""

from io import BytesIO

import pytest

from videos.threeplay_sync import (
    link_threeplay_files_as_resources,
    sync_video_captions_and_transcripts,
)
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import WebsiteContent

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
    # Create actual WebsiteContent objects with the 3Play-derived filenames so the
    # DB guard in each _attach_*_if_missing function can find them.
    transcript_resource = WebsiteContentFactory.create(
        website=website,
        filename="yt789_transcript",
    )
    captions_resource = WebsiteContentFactory.create(
        website=website,
        filename="yt789_captions",
    )
    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {
                "video_captions_resources": {
                    "content": [str(captions_resource.text_id)],
                    "website": website.name,
                },
                "video_transcript_resources": {
                    "content": [str(transcript_resource.text_id)],
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


def test_sync_video_captions_and_transcripts_appends_english_when_other_languages_exist(
    mocker,
):
    """3Play adds English even when other-language entries already exist from GDrive."""
    starter = WebsiteStarterFactory.create(slug="ocw-course-v2")
    website = WebsiteFactory.create(starter=starter)
    # Simulate GDrive having already linked French caption/transcript resources.
    # These use filenames that don't match the 3Play pattern, so the guard won't fire.
    fr_caption = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_captions_fr_vtt",
    )
    fr_transcript = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_transcript_fr_pdf",
    )
    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {
                "video_captions_resources": {
                    "content": [str(fr_caption.text_id)],
                    "website": website.name,
                },
                "video_transcript_resources": {
                    "content": [str(fr_transcript.text_id)],
                    "website": website.name,
                },
            },
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

    # French entries preserved; English appended
    transcript_content = vf["video_transcript_resources"]["content"]
    captions_content = vf["video_captions_resources"]["content"]
    assert str(fr_transcript.text_id) in transcript_content
    assert str(fr_caption.text_id) in captions_content
    assert len(transcript_content) == 2
    assert len(captions_content) == 2


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


def test_sync_video_captions_and_transcripts_appends_to_scalar_string_content(mocker):
    """A legacy scalar-string content value is normalized to a list, not exploded
    into characters, when 3Play appends a new resource id.
    """
    starter = WebsiteStarterFactory.create(slug="ocw-course-v2")
    website = WebsiteFactory.create(starter=starter)
    fr_caption = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_captions_fr_vtt",
    )
    fr_transcript = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_transcript_fr_pdf",
    )
    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {
                # Legacy single-item relation stored as a bare string, not a list
                "video_captions_resources": {
                    "content": str(fr_caption.text_id),
                    "website": website.name,
                },
                "video_transcript_resources": {
                    "content": str(fr_transcript.text_id),
                    "website": website.name,
                },
            },
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
    captions_content = vf["video_captions_resources"]["content"]
    transcript_content = vf["video_transcript_resources"]["content"]

    # Original id preserved whole, not exploded into individual characters
    assert str(fr_caption.text_id) in captions_content
    assert str(fr_transcript.text_id) in transcript_content
    assert len(captions_content) == 2
    assert len(transcript_content) == 2


def test_link_threeplay_files_as_resources(mocker):
    """Downloaded 3Play files become convention-named resources linked via _resources."""
    starter = WebsiteStarterFactory.create(slug="ocw-course-v2")
    website = WebsiteFactory.create(starter=starter)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        filename="lecture1_mp4",
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"youtube_id": "yt789"},
            "video_files": {},
        },
    )
    video = mocker.Mock()
    video.webvtt_transcript_file.name = "sites/site/threeplay.webvtt"
    video.webvtt_transcript_file.open.return_value.__enter__ = mocker.Mock(
        return_value=BytesIO(b"WEBVTT")
    )
    video.webvtt_transcript_file.open.return_value.__exit__ = mocker.Mock(
        return_value=False
    )
    video.pdf_transcript_file.name = "sites/site/threeplay.pdf"
    video.pdf_transcript_file.open.return_value.__enter__ = mocker.Mock(
        return_value=BytesIO(b"%PDF")
    )
    video.pdf_transcript_file.open.return_value.__exit__ = mocker.Mock(
        return_value=False
    )
    upload_mock = mocker.patch(
        "videos.threeplay_sync.upload_to_s3",
        side_effect=[
            f"/courses/{website.name}/lecture1_captions.vtt",
            f"/courses/{website.name}/lecture1_transcript.pdf",
        ],
    )

    changed = link_threeplay_files_as_resources(video, video_resource)

    assert changed is True
    assert upload_mock.call_count == 2
    # The uploaded files carry the video's convention-based names
    uploaded_names = [call.args[0].name for call in upload_mock.call_args_list]
    assert uploaded_names == ["lecture1.vtt", "lecture1.pdf"]

    vf = video_resource.metadata["video_files"]
    captions = WebsiteContent.objects.get(
        website=website, filename="lecture1_captions_vtt"
    )
    transcript = WebsiteContent.objects.get(
        website=website, filename="lecture1_transcript_pdf"
    )
    assert vf["video_captions_resources"]["content"] == [str(captions.text_id)]
    assert vf["video_transcript_resources"]["content"] == [str(transcript.text_id)]
    # Legacy _file fields in stored metadata are never written
    assert "video_captions_file" not in vf
    assert "video_transcript_file" not in vf


def test_link_threeplay_files_as_resources_no_files(mocker):
    """Nothing happens when the Video has no downloaded 3Play files."""
    website = WebsiteFactory.create()
    video_resource = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        filename="lecture1_mp4",
        metadata={"resourcetype": "Video", "video_files": {}},
    )
    video = mocker.Mock()
    video.webvtt_transcript_file = None
    video.pdf_transcript_file = None

    assert link_threeplay_files_as_resources(video, video_resource) is False
    assert video_resource.metadata["video_files"] == {}
