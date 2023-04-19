"""videos.signals tests"""
import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import TemporaryUploadedFile

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from videos.models import Video


@pytest.mark.django_db
def test_delete_video_file_signal(mocker):
    """Deleting a youtube VideoFile should trigger the Youtube API delete function"""
    mock_remove = mocker.patch("videos.signals.remove_youtube_video")
    mock_delete_s3_objects = mocker.patch("videos.signals.delete_s3_objects")
    video_file = VideoFileFactory.create(destination=DESTINATION_YOUTUBE)
    video_file.delete()
    mock_remove.delay.assert_called_once_with(video_file.destination_id)
    mock_delete_s3_objects.delay.assert_called_once_with(video_file.s3_key)


@pytest.mark.django_db
def test_delete_video_transcripts():
    """Deleting a Video object should delete related files."""
    pdf_temp_file = TemporaryUploadedFile(
        "transcript.pdf", "application/pdf", len("pdf"), None
    )
    pdf_temp_file.write(b"pdf")
    pdf_temp_file.seek(0)

    vtt_temp_file = TemporaryUploadedFile(
        "transcript.vtt", "text/vtt", len("vtt"), None
    )
    vtt_temp_file.write(b"vtt")
    vtt_temp_file.seek(0)

    video: Video = VideoFactory.create(
        pdf_transcript_file=pdf_temp_file, webvtt_transcript_file=vtt_temp_file
    )

    pdf_filename = video.pdf_transcript_file.name
    webvtt_filename = video.webvtt_transcript_file.name

    assert default_storage.exists(pdf_filename)
    assert default_storage.exists(webvtt_filename)

    video.delete()

    assert not default_storage.exists(pdf_filename)
    assert not default_storage.exists(webvtt_filename)
