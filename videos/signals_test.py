"""videos.signals tests"""
import pytest

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFileFactory


@pytest.mark.django_db
def test_delete_video_file_signal(mocker):
    """Deleting a youtube VideoFile should trigger the Youtube API delete function"""
    mock_remove = mocker.patch("videos.signals.remove_youtube_video")
    mock_delete_s3_objects = mocker.patch("videos.signals.delete_s3_objects")
    video_file = VideoFileFactory.create(destination=DESTINATION_YOUTUBE)
    video_file.delete()
    mock_remove.delay.assert_called_once_with(video_file.destination_id)
    mock_delete_s3_objects.delay.assert_called_once_with(video_file.s3_key)
