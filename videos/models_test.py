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
            website=video.website,
        )

    if has_caption:
        WebsiteContentFactory.create(
            filename=preexisting_captions_filenames["website_content"]["captions"],
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
