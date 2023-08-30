"""Video models tests"""
import pytest

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory

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
