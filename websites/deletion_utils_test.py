"""Tests for deletion utilities related to WebsiteContent."""

import pytest

import gdrive_sync.api as gdrive_api_module
from gdrive_sync.factories import DriveFileFactory
from gdrive_sync.models import DriveFile
from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.deletion_utils import (
    delete_related_captions_and_transcript,
    delete_resource,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


@pytest.mark.django_db()
def test_delete_pre_existing_video(mocker):
    """
    Deleting a pre-existing video should also delete its associated caption and transcript.
    """
    website = WebsiteFactory.create()

    mocker.patch("websites.deletion_utils.delete_drive_file")
    mocker.patch("websites.deletion_utils.get_drive_service")
    mocker.patch("websites.deletion_utils.delete_s3_objects")

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


@pytest.mark.django_db()
def test_delete_video_with_drive_files_comprehensive(mocker):
    """
    Deleting a video with associated drive files should:
     - Delete the video WebsiteContent object
     - Delete associated caption and transcript WebsiteContent objects
     - Delete associated DriveFile objects
     - Call external services for Google Drive and S3 cleanup
    """
    website = WebsiteFactory.create()

    mock_get_drive_service = mocker.patch("websites.deletion_utils.get_drive_service")
    mock_drive_service = mock_get_drive_service.return_value
    mocker.patch(
        "gdrive_sync.api.delete_drive_file", wraps=gdrive_api_module.delete_drive_file
    )
    mock_delete_s3_objects = mocker.patch("websites.deletion_utils.delete_s3_objects")
    mocker.patch("gdrive_sync.signals.delete_s3_objects")
    mocker.patch.object(DriveFile, "get_content_dependencies", return_value=[])

    base_name = "E8uZtq_vOYM"
    course_path = f"/courses/{website.name}/"
    caption_path = f"{course_path}{base_name}_captions.vtt"
    transcript_path = f"{course_path}{base_name}_transcript.pdf"
    video_path = f"{course_path}{base_name}.mp4"

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
        file=video_path,
    )
    caption = WebsiteContentFactory.create(
        website=website, file=caption_path, filename=f"{base_name}_captions"
    )
    transcript = WebsiteContentFactory.create(
        website=website, file=transcript_path, filename=f"{base_name}_transcript"
    )

    video_drive_file = DriveFileFactory.create(
        resource=video,
        website=website,
        file_id="video_drive_file_id",
        s3_key=f"s3/{video_path}",
    )
    caption_drive_file = DriveFileFactory.create(
        resource=caption,
        website=website,
        file_id="caption_drive_file_id",
        s3_key=f"s3/{caption_path}",
    )
    transcript_drive_file = DriveFileFactory.create(
        resource=transcript,
        website=website,
        file_id="transcript_drive_file_id",
        s3_key=f"s3/{transcript_path}",
    )

    # Assert objects exist
    assert WebsiteContent.objects.filter(pk=video.pk).exists()
    assert WebsiteContent.objects.filter(pk=caption.pk).exists()
    assert WebsiteContent.objects.filter(pk=transcript.pk).exists()
    assert DriveFile.objects.filter(pk=video_drive_file.pk).exists()
    assert DriveFile.objects.filter(pk=caption_drive_file.pk).exists()
    assert DriveFile.objects.filter(pk=transcript_drive_file.pk).exists()

    # Trigger deletion
    delete_related_captions_and_transcript(video)
    delete_resource(video)

    # Assert objects are gone
    assert not WebsiteContent.objects.filter(pk=video.pk).exists()
    assert not WebsiteContent.objects.filter(pk=caption.pk).exists()
    assert not WebsiteContent.objects.filter(pk=transcript.pk).exists()
    assert not DriveFile.objects.filter(pk=video_drive_file.pk).exists()
    assert not DriveFile.objects.filter(pk=caption_drive_file.pk).exists()
    assert not DriveFile.objects.filter(pk=transcript_drive_file.pk).exists()

    # Verify external deletions
    assert mock_drive_service.files().delete.call_count == 3
    drive_ids = [
        call.kwargs["fileId"]
        for call in mock_drive_service.files().delete.call_args_list
    ]
    for fid in (
        "video_drive_file_id",
        "caption_drive_file_id",
        "transcript_drive_file_id",
    ):
        assert fid in drive_ids

    assert mock_delete_s3_objects.delay.call_count == 3
    s3_keys = [
        call.kwargs["key"] for call in mock_delete_s3_objects.delay.call_args_list
    ]
    for key in (f"s3/{video_path}", f"s3/{caption_path}", f"s3/{transcript_path}"):
        assert key in s3_keys


@pytest.mark.django_db()
def test_delete_video_mixed_scenario(mocker):
    """
    Test mixed scenario: Video has drive file, but caption/transcript don't.
    """
    website = WebsiteFactory.create()

    mock_delete_drive_file = mocker.patch("websites.deletion_utils.delete_drive_file")
    mock_get_drive_service = mocker.patch("websites.deletion_utils.get_drive_service")
    mock_drive_service = mock_get_drive_service.return_value
    mock_delete_s3_objects = mocker.patch("websites.deletion_utils.delete_s3_objects")
    mocker.patch("gdrive_sync.signals.delete_s3_objects")
    mock_delete_drive_file.side_effect = (
        lambda drive_file, **kwargs: drive_file.delete()  # noqa: ARG005
    )

    base_name = "E8uZtq_vOYM"
    course_path = f"/courses/{website.name}/"

    video_metadata = {
        "resourcetype": RESOURCE_TYPE_VIDEO,
        "video_files": {
            "video_captions_file": f"{course_path}{base_name}_captions.vtt",
            "video_transcript_file": f"{course_path}{base_name}_transcript.pdf",
        },
    }

    video = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata=video_metadata,
        file=f"{course_path}{base_name}.mp4",
    )
    caption = WebsiteContentFactory.create(
        website=website, file=f"{course_path}{base_name}_captions.vtt"
    )
    transcript = WebsiteContentFactory.create(
        website=website, file=f"{course_path}{base_name}_transcript.pdf"
    )

    video_drive_file = DriveFileFactory.create(
        resource=video,
        website=website,
        file_id="video_drive_file_id",
        s3_key=f"s3/{course_path}{base_name}.mp4",
    )

    drive_file_id = video_drive_file.file_id

    assert WebsiteContent.objects.filter(pk=video.pk).exists()
    assert WebsiteContent.objects.filter(pk=caption.pk).exists()
    assert WebsiteContent.objects.filter(pk=transcript.pk).exists()
    assert DriveFile.objects.filter(file_id=drive_file_id).exists()

    # Perform deletion
    delete_related_captions_and_transcript(video)
    delete_resource(video)

    # Post-delete checks
    assert not WebsiteContent.objects.filter(pk=video.pk).exists()
    assert not WebsiteContent.objects.filter(pk=caption.pk).exists()
    assert not WebsiteContent.objects.filter(pk=transcript.pk).exists()
    assert not DriveFile.objects.filter(file_id=drive_file_id).exists()

    # Assertions on mock calls
    mock_delete_drive_file.assert_called_once()
    mock_drive_service.files().delete.assert_called_once_with(
        fileId=drive_file_id, supportsAllDrives=True
    )
    mock_delete_s3_objects.delay.assert_called_once_with(
        key=f"s3/{course_path}{base_name}.mp4"
    )
