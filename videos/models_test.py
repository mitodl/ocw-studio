"""Video models tests"""

import pytest

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.site_config_api import SiteConfig

# pylint:disable=unused-argument,redefined-outer-name
pytestmark = pytest.mark.django_db


def test_video_youtube_id():
    """Test for Video youtube_id"""
    video = VideoFactory.create()
    assert video.youtube_id() is None
    VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, video=video, destination_id="expected_id"
    )
    assert video.youtube_id() == "expected_id"


@pytest.mark.parametrize("has_transcript", [True, False])
@pytest.mark.parametrize("has_caption", [True, False])
def test_video_caption_transcript_resources(
    has_transcript, has_caption, preexisting_captions_filenames
):
    """Test caption_transcript_resources finds appropriate resources for video"""
    youtube_id = "yt-id"

    video = VideoFactory.create()
    VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, video=video, destination_id=youtube_id
    )
    WebsiteContentFactory.create(
        metadata={"video_metadata": {"youtube_id": youtube_id}},
        filename=preexisting_captions_filenames["website_content"]["video"],
        website=video.website,
    )

    if has_transcript:
        WebsiteContentFactory.create(
            filename=preexisting_captions_filenames["website_content"]["transcript"],
            file=f"courses/{video.website.name}/file_transcript.pdf",
            website=video.website,
        )

    if has_caption:
        WebsiteContentFactory.create(
            filename=preexisting_captions_filenames["website_content"]["captions"],
            file=f"courses/{video.website.name}/file_captions.vtt",
            website=video.website,
        )

    captions, transcript = video.caption_transcript_resources()

    assert bool(captions) == has_caption
    assert bool(transcript) == has_transcript


def test_video_upload_file_to(course_starter):
    """Test upload_file_to generates the expected path"""
    website = WebsiteFactory.create(starter=course_starter, name="website-name")

    video = VideoFactory.create(
        website=website, source_key="gdrive_uploads/hash/file.ext"
    )

    filename = "filename.ext"
    expected_upload_location = f"{SiteConfig(course_starter.config).root_url_path}/website-name/hash_{filename}".lstrip(
        "/"
    )

    upload_location = video.upload_file_to(filename)
    assert upload_location == expected_upload_location


@pytest.mark.django_db
def test_video_caption_transcript_resources_multi_language(
    preexisting_captions_filenames,
):
    """caption_transcript_resources returns all language-tagged captions/transcripts."""
    youtube_id = "yt-multi"

    video = VideoFactory.create()
    VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, video=video, destination_id=youtube_id
    )
    video_filename = preexisting_captions_filenames["website_content"]["video"]
    WebsiteContentFactory.create(
        metadata={"video_metadata": {"youtube_id": youtube_id}},
        filename=video_filename,
        website=video.website,
    )
    # Strip trailing suffix (e.g. "_mp4") to get the base stem
    base = "_".join(video_filename.rsplit("_", 1)[:-1])
    WebsiteContentFactory.create(
        filename=f"{base}_captions_en_vtt",
        file=f"courses/{video.website.name}/{base}_captions_en.vtt",
        website=video.website,
    )
    WebsiteContentFactory.create(
        filename=f"{base}_captions_es_vtt",
        file=f"courses/{video.website.name}/{base}_captions_es.vtt",
        website=video.website,
    )
    WebsiteContentFactory.create(
        filename=f"{base}_transcript_fr_pdf",
        file=f"courses/{video.website.name}/{base}_transcript_fr.pdf",
        website=video.website,
    )

    captions, transcripts = video.caption_transcript_resources()

    assert len(captions) == 2
    assert len(transcripts) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("filename_suffix", ["_vtt", "_webvtt"])
def test_video_caption_transcript_resources_matches_all_extensions(
    filename_suffix, preexisting_captions_filenames
):
    """caption_transcript_resources finds captions regardless of extension.

    A caption file may slugify to _vtt or _webvtt depending on its source
    extension (3Play produces .webvtt). Both must be found. srt is
    deliberately excluded - it's not natively playable via the HTML5
    <track> element (see test_start_transcript_job's wrong_caption_type).
    """
    youtube_id = "yt-ext"

    video = VideoFactory.create()
    VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, video=video, destination_id=youtube_id
    )
    video_filename = preexisting_captions_filenames["website_content"]["video"]
    WebsiteContentFactory.create(
        metadata={"video_metadata": {"youtube_id": youtube_id}},
        filename=video_filename,
        website=video.website,
    )
    base = "_".join(video_filename.rsplit("_", 1)[:-1])
    extension = filename_suffix.lstrip("_")
    WebsiteContentFactory.create(
        filename=f"{base}_captions-en-us{filename_suffix}",
        file=f"courses/{video.website.name}/{base}_captions-en-US.{extension}",
        website=video.website,
    )

    captions, _ = video.caption_transcript_resources()

    assert len(captions) == 1


@pytest.mark.django_db
def test_video_caption_transcript_resources_survives_filename_uniqueness_suffix(
    preexisting_captions_filenames,
):
    """caption_transcript_resources still matches when Django's filename-uniqueness
    logic has appended a bare digit to the colliding filename (e.g. "..._vtt2").

    This is the actual production bug: matching must rely on the resource's real
    uploaded file extension, not the filename field, since find_available_name
    can mutate the filename's tail with no separator.
    """
    youtube_id = "yt-collision"

    video = VideoFactory.create()
    VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, video=video, destination_id=youtube_id
    )
    video_filename = preexisting_captions_filenames["website_content"]["video"]
    WebsiteContentFactory.create(
        metadata={"video_metadata": {"youtube_id": youtube_id}},
        filename=video_filename,
        website=video.website,
    )
    base = "_".join(video_filename.rsplit("_", 1)[:-1])
    # Simulates a second same-named upload: find_available_name would produce
    # this exact filename by appending "2" directly onto "..._vtt" / "..._pdf".
    WebsiteContentFactory.create(
        filename=f"{base}_captions-en-us_vtt2",
        file=f"courses/{video.website.name}/{base}_captions-en-US.vtt",
        website=video.website,
    )
    WebsiteContentFactory.create(
        filename=f"{base}_transcript-en-us_pdf2",
        file=f"courses/{video.website.name}/{base}_transcript-en-US.pdf",
        website=video.website,
    )

    captions, transcripts = video.caption_transcript_resources()

    assert len(captions) == 1
    assert len(transcripts) == 1
