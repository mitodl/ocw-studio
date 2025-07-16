"""Tests for deletion utilities related to WebsiteContent."""

import pytest

from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.deletion_utils import (
    delete_related_captions_and_transcript,
    delete_resource,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


@pytest.mark.django_db()
def test_delete_video_deletes_captions_and_transcripts(mocker):
    """
    Deleting a video should also delete its associated caption and transcript WebsiteContent
    objects.
    """
    website = WebsiteFactory.create()

    mocker.patch("websites.deletion_utils.delete_drive_file")
    mocker.patch("websites.deletion_utils.get_drive_service")
    mocker.patch("websites.deletion_utils.delete_s3_objects.delay")

    base_name = "E8uZtq_vOYM"
    course_path = f"/courses/{website.name}/"
    caption_path = f"{course_path}{base_name}_captions.vtt"
    transcript_path = f"{course_path}{base_name}_transcript.pdf"

    video_metadata = {
        "resourcetype": RESOURCE_TYPE_VIDEO,
        "video_files": {
            "video_captions_file": caption_path,
            "video_transcript_file": transcript_path,
        },
    }

    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata=video_metadata,
    )

    caption = WebsiteContentFactory.create(
        website=website, file=caption_path, filename=f"{base_name}_captions"
    )
    transcript = WebsiteContentFactory.create(
        website=website, file=transcript_path, filename=f"{base_name}_transcript"
    )

    assert WebsiteContent.objects.filter(pk=video.pk).exists()
    assert WebsiteContent.objects.filter(pk=caption.pk).exists()
    assert WebsiteContent.objects.filter(pk=transcript.pk).exists()

    delete_related_captions_and_transcript(video)
    delete_resource(video)

    assert not WebsiteContent.objects.filter(pk=video.pk).exists()
    assert not WebsiteContent.objects.filter(pk=caption.pk).exists()
    assert not WebsiteContent.objects.filter(pk=transcript.pk).exists()
