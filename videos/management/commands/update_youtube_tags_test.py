"""Tests for the update_youtube_tags management command"""

import pytest
from django.core.management import call_command

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_youtube_api(mocker):
    """Mock the YouTube API client"""
    mock_api_cls = mocker.patch(
        "videos.management.commands.update_youtube_tags.YouTubeApi"
    )
    return mock_api_cls.return_value


@pytest.fixture
def video_content_with_tags():
    """Create a video content resource with tags"""
    website = WebsiteFactory.create(name="test-course", short_id="test-course")
    video = VideoFactory.create(website=website)
    video_file = VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="test_youtube_id_123",
    )

    content = WebsiteContentFactory.create(
        website=website,
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "test_youtube_id_123",
                "video_tags": "python, django, testing",
                "youtube_description": "A test video description",
            },
        },
    )
    return content, video_file


def test_update_youtube_tags_dry_run(mock_youtube_api, video_content_with_tags):
    """Test that dry-run mode doesn't actually update YouTube"""
    _content, _video_file = video_content_with_tags

    call_command(
        "update_youtube_tags",
        filter="test-course",
        dry_run=True,
    )

    mock_youtube_api.update_video_tags.assert_not_called()


def test_update_youtube_tags_success(mock_youtube_api, video_content_with_tags):
    """Test that the command successfully updates YouTube tags"""
    _content, _video_file = video_content_with_tags

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    mock_youtube_api.update_video_tags.assert_called_once_with(
        "test_youtube_id_123", "python, django, testing"
    )


def test_update_youtube_tags_specific_video(mock_youtube_api):
    """Test updating tags for a specific YouTube ID"""
    website = WebsiteFactory.create(name="test-course")

    # Create two videos
    video1 = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video1,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_id_1",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video 1",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_id_1",
                "video_tags": "tag1",
            },
        },
    )

    video2 = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video2,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_id_2",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video 2",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_id_2",
                "video_tags": "tag2",
            },
        },
    )

    call_command(
        "update_youtube_tags",
        youtube_id="youtube_id_1",
    )

    # Should only update the video with youtube_id_1
    mock_youtube_api.update_video_tags.assert_called_once_with("youtube_id_1", "tag1")


def test_update_youtube_tags_no_tags(mock_youtube_api):
    """Test handling of videos without tags"""
    website = WebsiteFactory.create(name="test-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_id_no_tags",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video Without Tags",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_id_no_tags",
            },
        },
    )

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should still update, even with empty tags
    mock_youtube_api.update_video_tags.assert_called_once_with("youtube_id_no_tags", "")


def test_update_youtube_tags_missing_youtube_id(mock_youtube_api):
    """Test skipping videos without YouTube ID"""
    website = WebsiteFactory.create(name="test-course")
    WebsiteContentFactory.create(
        website=website,
        title="Video Without YouTube ID",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {},
        },
    )

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should not call update for videos without YouTube ID
    mock_youtube_api.update_video_tags.assert_not_called()


def test_update_youtube_tags_api_error(mock_youtube_api, video_content_with_tags):
    """Test handling of YouTube API errors"""
    _content, _video_file = video_content_with_tags
    mock_youtube_api.update_video_tags.side_effect = Exception("YouTube API error")

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should have attempted to call update despite error
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "test_youtube_id_123", "python, django, testing"
    )


def test_update_youtube_tags_youtube_not_enabled(mocker):
    """Test that command exits if YouTube is not enabled"""
    mocker.patch(
        "videos.management.commands.update_youtube_tags.is_youtube_enabled",
        return_value=False,
    )

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Command should exit early without processing


def test_update_youtube_tags_no_videos_found(mock_youtube_api):
    """Test handling when no videos match the criteria"""
    WebsiteFactory.create(name="empty-course")

    call_command(
        "update_youtube_tags",
        filter="empty-course",
    )

    # Should not call update when no videos found
    mock_youtube_api.update_video_tags.assert_not_called()


def test_update_youtube_tags_exclude_filter(mock_youtube_api):
    """Test excluding specific websites"""
    website1 = WebsiteFactory.create(name="course-1")
    video1 = VideoFactory.create(website=website1)
    VideoFileFactory.create(
        video=video1,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_1",
    )
    WebsiteContentFactory.create(
        website=website1,
        title="Video 1",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {"youtube_id": "youtube_1", "video_tags": "tag1"},
        },
    )

    website2 = WebsiteFactory.create(name="course-2")
    video2 = VideoFactory.create(website=website2)
    VideoFileFactory.create(
        video=video2,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_2",
    )
    WebsiteContentFactory.create(
        website=website2,
        title="Video 2",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {"youtube_id": "youtube_2", "video_tags": "tag2"},
        },
    )

    call_command(
        "update_youtube_tags",
        exclude="course-2",
    )

    # Should only update video from course-1
    mock_youtube_api.update_video_tags.assert_called_once_with("youtube_1", "tag1")


def test_update_youtube_tags_add_course_tag(mock_youtube_api):
    """Test adding course URL slug as a tag"""
    website = WebsiteFactory.create(
        name="course-with-videos",
        short_id="cwv",
        url_path="courses/course-with-videos",
    )
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_test_123",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_test_123",
                "video_tags": "python, django",
            },
        },
    )

    call_command(
        "update_youtube_tags",
        filter="course-with-videos",
        add_course_tag=True,
    )

    # Verify the tags were merged with the course URL slug (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "youtube_test_123", "python, django, course-with-videos"
    )


def test_update_youtube_tags_add_course_tag_no_existing_tags(mock_youtube_api):
    """Test adding course URL slug as a tag when no existing tags"""
    website = WebsiteFactory.create(
        name="test-course-123", url_path="courses/test-course-123"
    )
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_id_789",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video Without Tags",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_id_789",
            },
        },
    )

    call_command(
        "update_youtube_tags",
        filter="test-course-123",
        add_course_tag=True,
    )

    # Verify course URL slug was added as the only tag
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_id_789", "test-course-123"
    )


def test_update_youtube_tags_add_course_tag_already_exists(mock_youtube_api):
    """Test that course URL slug isn't duplicated if already in tags"""
    website = WebsiteFactory.create(name="my-course", url_path="courses/my-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_existing",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_existing",
                "video_tags": "python, my-course, django",
            },
        },
    )

    call_command(
        "update_youtube_tags",
        filter="my-course",
        add_course_tag=True,
    )

    # Verify course URL slug wasn't duplicated (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_existing", "python, my-course, django"
    )


def test_update_youtube_tags_saves_metadata_to_database(mock_youtube_api):
    """Test that merged tags are saved to the database"""
    website = WebsiteFactory.create(name="test-course", url_path="courses/test-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_save_test",
    )
    content = WebsiteContentFactory.create(
        website=website,
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_save_test",
                "video_tags": "python, django",
            },
        },
    )

    # Get initial tags
    initial_tags = content.metadata["video_metadata"]["video_tags"]
    assert initial_tags == "python, django"

    call_command(
        "update_youtube_tags",
        filter="test-course",
        add_course_tag=True,
    )

    # Verify YouTube API was called
    assert mock_youtube_api.update_video_tags.called

    # Refresh from database to verify persistence
    content.refresh_from_db()
    updated_tags = content.metadata["video_metadata"]["video_tags"]

    # Verify tags were merged and saved to database (alphabetically sorted)
    assert "test-course" in updated_tags
    assert "python" in updated_tags
    assert "django" in updated_tags
    assert updated_tags == "python, django, test-course"


def test_update_youtube_tags_dry_run_does_not_save_metadata(mock_youtube_api):
    """Test that dry-run mode doesn't save metadata to database"""
    website = WebsiteFactory.create(name="test-course", url_path="courses/test-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_dry_run_test",
    )
    content = WebsiteContentFactory.create(
        website=website,
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_dry_run_test",
                "video_tags": "python, django",
            },
        },
    )

    initial_tags = content.metadata["video_metadata"]["video_tags"]

    call_command(
        "update_youtube_tags",
        filter="test-course",
        add_course_tag=True,
        dry_run=True,
    )

    # Verify YouTube API was NOT called in dry-run mode
    assert not mock_youtube_api.update_video_tags.called

    # Refresh from database
    content.refresh_from_db()
    tags_after_dry_run = content.metadata["video_metadata"]["video_tags"]

    # Verify tags were NOT modified in database during dry-run
    assert tags_after_dry_run == initial_tags
    assert tags_after_dry_run == "python, django"
    assert "test-course" not in tags_after_dry_run
