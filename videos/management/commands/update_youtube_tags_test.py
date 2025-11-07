"""Tests for the update_youtube_tags management command"""

from io import StringIO

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

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course",
        dry_run=True,
        stdout=out,
    )

    output = out.getvalue()
    assert "DRY RUN MODE" in output
    assert "[DRY RUN] Would update tags on YouTube" in output
    assert "Successfully updated: 1" in output
    mock_youtube_api.update_video.assert_not_called()


def test_update_youtube_tags_success(mock_youtube_api, video_content_with_tags):
    """Test that the command successfully updates YouTube tags"""
    content, _video_file = video_content_with_tags

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course",
        stdout=out,
    )

    output = out.getvalue()
    assert "Processing: Test Video" in output
    assert "YouTube ID: test_youtube_id_123" in output
    assert "Tags: python, django, testing" in output
    assert "Successfully updated: 1" in output
    mock_youtube_api.update_video.assert_called_once_with(content, privacy=None)


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
    content1 = WebsiteContentFactory.create(
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
    _content2 = WebsiteContentFactory.create(
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

    out = StringIO()
    call_command(
        "update_youtube_tags",
        youtube_id="youtube_id_1",
        stdout=out,
    )

    output = out.getvalue()
    assert "Video 1" in output
    assert "Video 2" not in output
    assert "Successfully updated: 1" in output
    mock_youtube_api.update_video.assert_called_once_with(content1, privacy=None)


def test_update_youtube_tags_no_tags(mock_youtube_api):
    """Test handling of videos without tags"""
    website = WebsiteFactory.create(name="test-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_id_no_tags",
    )
    content = WebsiteContentFactory.create(
        website=website,
        title="Video Without Tags",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_id_no_tags",
            },
        },
    )

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course",
        stdout=out,
    )

    output = out.getvalue()
    assert "Tags: (no tags)" in output
    assert "Successfully updated: 1" in output
    mock_youtube_api.update_video.assert_called_once_with(content, privacy=None)


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

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course",
        stdout=out,
    )

    output = out.getvalue()
    assert "Skipped: 1" in output
    mock_youtube_api.update_video.assert_not_called()


def test_update_youtube_tags_api_error(mock_youtube_api, video_content_with_tags):
    """Test handling of YouTube API errors"""
    _content, _video_file = video_content_with_tags
    mock_youtube_api.update_video.side_effect = Exception("YouTube API error")

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course",
        stdout=out,
    )

    output = out.getvalue()
    assert "Error updating tags" in output
    assert "YouTube API error" in output
    assert "Errors: 1" in output


def test_update_youtube_tags_youtube_not_enabled(mocker):
    """Test that command exits if YouTube is not enabled"""
    mocker.patch(
        "videos.management.commands.update_youtube_tags.is_youtube_enabled",
        return_value=False,
    )

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course",
        stdout=out,
    )

    output = out.getvalue()
    assert "YouTube integration is not enabled" in output


def test_update_youtube_tags_no_videos_found(mock_youtube_api):
    """Test handling when no videos match the criteria"""
    WebsiteFactory.create(name="empty-course")

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="empty-course",
        stdout=out,
    )

    output = out.getvalue()
    assert "No video resources found" in output
    mock_youtube_api.update_video.assert_not_called()


def test_update_youtube_tags_exclude_filter(mock_youtube_api):
    """Test excluding specific websites"""
    website1 = WebsiteFactory.create(name="course-1")
    video1 = VideoFactory.create(website=website1)
    VideoFileFactory.create(
        video=video1,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_1",
    )
    content1 = WebsiteContentFactory.create(
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

    out = StringIO()
    call_command(
        "update_youtube_tags",
        exclude="course-2",
        stdout=out,
    )

    output = out.getvalue()
    assert "Video 1" in output
    assert "Video 2" not in output
    assert "Successfully updated: 1" in output
    mock_youtube_api.update_video.assert_called_once_with(content1, privacy=None)


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
    _content = WebsiteContentFactory.create(
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

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="course-with-videos",
        add_course_tag=True,
        stdout=out,
    )

    output = out.getvalue()
    assert "Adding course name as tag for all videos" in output
    assert "Course tag added: course-with-videos" in output
    assert "Successfully updated: 1" in output

    # Verify the tags were merged with the course URL slug
    mock_youtube_api.update_video.assert_called_once()
    updated_content = mock_youtube_api.update_video.call_args[0][0]
    tags = updated_content.metadata["video_metadata"]["video_tags"]
    assert "course-with-videos" in tags
    assert "python" in tags
    assert "django" in tags


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
    _content = WebsiteContentFactory.create(
        website=website,
        title="Video Without Tags",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_id_789",
            },
        },
    )

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="test-course-123",
        add_course_tag=True,
        stdout=out,
    )

    output = out.getvalue()
    assert "Successfully updated: 1" in output

    # Verify course URL slug was added as the only tag
    mock_youtube_api.update_video.assert_called_once()
    updated_content = mock_youtube_api.update_video.call_args[0][0]
    tags = updated_content.metadata["video_metadata"]["video_tags"]
    assert tags == "test-course-123"


def test_update_youtube_tags_add_course_tag_already_exists(mock_youtube_api):
    """Test that course URL slug isn't duplicated if already in tags"""
    website = WebsiteFactory.create(name="my-course", url_path="courses/my-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_existing",
    )
    _content = WebsiteContentFactory.create(
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

    out = StringIO()
    call_command(
        "update_youtube_tags",
        filter="my-course",
        add_course_tag=True,
        stdout=out,
    )

    # Verify course URL slug wasn't duplicated
    mock_youtube_api.update_video.assert_called_once()
    updated_content = mock_youtube_api.update_video.call_args[0][0]
    tags = updated_content.metadata["video_metadata"]["video_tags"]
    # Should appear only once
    assert tags.count("my-course") == 1
    assert "python" in tags
    assert "django" in tags
