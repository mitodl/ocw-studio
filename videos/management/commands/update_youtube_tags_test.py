"""Tests for the update_youtube_tags management command"""

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command

from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from videos.management.commands.update_youtube_tags import Command
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import WebsiteContent

pytestmark = pytest.mark.django_db

# Load OCW course config for tests
COURSE_STARTER_CONFIG = yaml.safe_load(
    (
        Path(settings.BASE_DIR) / "localdev/configs/ocw-course-site-config.yml"
    ).read_text()
)


@pytest.fixture
def mock_youtube_api(mocker):
    """Mock the YouTube API client"""
    mock_api_cls = mocker.patch(
        "videos.management.commands.update_youtube_tags.YouTubeApi"
    )
    mock_api = mock_api_cls.return_value

    # Mock the client.videos().list() chain to return current YouTube tags
    mock_list_response = {
        "items": [
            {
                "snippet": {
                    "tags": []  # Default: no tags on YouTube
                }
            }
        ]
    }
    mock_api.client.videos.return_value.list.return_value.execute.return_value = (
        mock_list_response
    )

    return mock_api


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
    """Test that dry-run mode doesn't actually update YouTube or save to DB"""
    content, _ = video_content_with_tags
    initial_tags = content.metadata["video_metadata"]["video_tags"]

    # Mock YouTube returning some tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["youtube-tag"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
        dry_run=True,
    )

    # Should fetch from YouTube but not update
    assert mock_youtube_api.client.videos.return_value.list.called
    mock_youtube_api.update_video_tags.assert_not_called()

    # Verify DB was not modified
    content.refresh_from_db()
    assert content.metadata["video_metadata"]["video_tags"] == initial_tags


def test_update_youtube_tags_success(mock_youtube_api, video_content_with_tags):
    """Test that the command successfully merges and updates YouTube tags"""
    content, _ = video_content_with_tags

    # Mock YouTube already having some tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["existing-youtube-tag"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should merge YouTube tags (existing-youtube-tag) with DB tags (python, django, testing)
    # Tags are sorted alphabetically
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "test_youtube_id_123", "django, existing-youtube-tag, python, testing"
    )

    # Verify merged tags saved to DB
    content.refresh_from_db()
    final_db_tags = content.metadata["video_metadata"]["video_tags"]
    assert "existing-youtube-tag" in final_db_tags
    assert "python" in final_db_tags
    assert "django" in final_db_tags
    assert "testing" in final_db_tags
    # Verify exact final state: normalized (lowercase), sorted, no duplicates
    assert final_db_tags == "django, existing-youtube-tag, python, testing"


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

    # Mock YouTube response for youtube_id_1
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["youtube-tag"]}}]
    }

    call_command(
        "update_youtube_tags",
        youtube_id="youtube_id_1",
    )

    # Should only update the video with youtube_id_1, merging its tags (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "youtube_id_1", "tag1, youtube-tag"
    )

    # Verify tags saved to DB for video 1
    content1 = WebsiteContent.objects.get(
        website=website, metadata__video_metadata__youtube_id="youtube_id_1"
    )
    content1.refresh_from_db()
    assert content1.metadata["video_metadata"]["video_tags"] == "tag1, youtube-tag"

    # Verify video 2 was NOT updated
    content2 = WebsiteContent.objects.get(
        website=website, metadata__video_metadata__youtube_id="youtube_id_2"
    )
    content2.refresh_from_db()
    assert content2.metadata["video_metadata"]["video_tags"] == "tag2"


def test_update_youtube_tags_multiple_youtube_ids(mock_youtube_api):
    """Test updating multiple videos with comma-separated YouTube IDs"""
    website = WebsiteFactory.create(name="test-course")

    # Create three videos
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

    video3 = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video3,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_id_3",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video 3",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_id_3",
                "video_tags": "tag3",
            },
        },
    )

    def mock_list(*args, **kwargs):
        youtube_id = kwargs.get("id")
        mock_execute = (
            mock_youtube_api.client.videos.return_value.list.return_value.execute
        )

        if youtube_id == "youtube_id_1":
            mock_execute.return_value = {
                "items": [{"snippet": {"tags": ["youtube-tag1"]}}]
            }
        elif youtube_id == "youtube_id_2":
            mock_execute.return_value = {
                "items": [{"snippet": {"tags": ["youtube-tag2"]}}]
            }
        else:
            mock_execute.return_value = {"items": [{"snippet": {"tags": []}}]}

        return mock_youtube_api.client.videos.return_value.list.return_value

    mock_youtube_api.client.videos.return_value.list.side_effect = mock_list

    # Test with comma-separated YouTube IDs
    call_command(
        "update_youtube_tags",
        youtube_id="youtube_id_1, youtube_id_2",  # Note the space after comma
    )

    # Should update both videos (but not video 3)
    assert mock_youtube_api.update_video_tags.call_count == 2

    # Verify the calls were made with correct merged tags
    calls = mock_youtube_api.update_video_tags.call_args_list
    call_args = {call[0][0]: call[0][1] for call in calls}

    assert "youtube_id_1" in call_args
    assert call_args["youtube_id_1"] == "tag1, youtube-tag1"

    assert "youtube_id_2" in call_args
    assert call_args["youtube_id_2"] == "tag2, youtube-tag2"


def test_update_youtube_tags_no_tags(mock_youtube_api):
    """Test handling of videos without tags in DB or YouTube"""
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

    # Mock YouTube also having no tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": []}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should skip update when no tags in either location
    mock_youtube_api.update_video_tags.assert_not_called()


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
    # Mock YouTube list call failing
    mock_youtube_api.client.videos.return_value.list.return_value.execute.side_effect = Exception(
        "YouTube API error"
    )

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should not call update if list() fails
    mock_youtube_api.update_video_tags.assert_not_called()


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

    # Mock YouTube having different tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["yt-tag"]}}]
    }

    call_command(
        "update_youtube_tags",
        exclude="course-2",
    )

    # Should only update video from course-1, merging tags (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "youtube_1", "tag1, yt-tag"
    )


def test_update_youtube_tags_add_course_tag(mock_youtube_api):
    """Test adding course URL slug as a tag while merging YouTube and DB tags"""
    starter = WebsiteStarterFactory.create(config=COURSE_STARTER_CONFIG)
    website = WebsiteFactory.create(
        name="course-with-videos",
        short_id="cwv",
        url_path="courses/course-with-videos",
        starter=starter,
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

    # Mock YouTube having additional tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["machine-learning"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="course-with-videos",
        add_course_tag=True,
    )

    # Verify the tags were merged: YouTube tags + DB tags + course slug (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "youtube_test_123", "course-with-videos, django, machine-learning, python"
    )


def test_update_youtube_tags_add_course_tag_no_existing_tags(mock_youtube_api):
    """Test adding course URL slug when no tags in DB but some on YouTube"""
    starter = WebsiteStarterFactory.create(config=COURSE_STARTER_CONFIG)
    website = WebsiteFactory.create(
        name="test-course-123",
        url_path="courses/test-course-123",
        starter=starter,
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

    # Mock YouTube having some tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["existing-yt-tag"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course-123",
        add_course_tag=True,
    )

    # Verify YouTube tag + course slug were merged (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_id_789", "existing-yt-tag, test-course-123"
    )

    # Verify final tags in DB include both YouTube tag and course slug
    content = WebsiteContent.objects.get(
        website=website, metadata__video_metadata__youtube_id="yt_id_789"
    )
    content.refresh_from_db()
    final_db_tags = content.metadata["video_metadata"]["video_tags"]
    assert final_db_tags == "existing-yt-tag, test-course-123"
    assert "existing-yt-tag" in final_db_tags
    assert "test-course-123" in final_db_tags


def test_update_youtube_tags_add_course_tag_already_exists(mock_youtube_api):
    """Test that course URL slug isn't duplicated if already on YouTube"""
    starter = WebsiteStarterFactory.create(config=COURSE_STARTER_CONFIG)
    website = WebsiteFactory.create(
        name="my-course",
        url_path="courses/my-course",
        starter=starter,
    )
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
                "video_tags": "python, django",
            },
        },
    )

    # Mock YouTube already having the course tag
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["my-course", "machine-learning"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="my-course",
        add_course_tag=True,
    )

    # Verify course URL slug wasn't duplicated, tags properly merged (alphabetically sorted)
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_existing", "django, machine-learning, my-course, python"
    )

    # Verify final tags in DB: all tags merged, no duplicates, alphabetically sorted
    content = WebsiteContent.objects.get(
        website=website, metadata__video_metadata__youtube_id="yt_existing"
    )
    content.refresh_from_db()
    final_db_tags = content.metadata["video_metadata"]["video_tags"]
    assert final_db_tags == "django, machine-learning, my-course, python"
    # Ensure course tag appears only once (not duplicated)
    assert final_db_tags.count("my-course") == 1


def test_update_youtube_tags_saves_metadata_to_database(mock_youtube_api):
    """Test that merged YouTube + DB tags are saved to the database"""
    starter = WebsiteStarterFactory.create(config=COURSE_STARTER_CONFIG)
    website = WebsiteFactory.create(
        name="test-course",
        url_path="courses/test-course",
        starter=starter,
    )
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

    # Mock YouTube having additional tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["ai", "machine-learning"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
        add_course_tag=True,
    )

    # Verify YouTube API was called with merged tags (alphabetically sorted)
    assert mock_youtube_api.update_video_tags.called
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_save_test", "ai, django, machine-learning, python, test-course"
    )

    # Refresh from database to verify persistence
    content.refresh_from_db()
    updated_tags = content.metadata["video_metadata"]["video_tags"]

    # Verify all tags were merged and saved to database (alphabetically sorted)
    assert "test-course" in updated_tags
    assert "python" in updated_tags
    assert "django" in updated_tags
    assert "ai" in updated_tags
    assert "machine-learning" in updated_tags
    assert updated_tags == "ai, django, machine-learning, python, test-course"


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

    # Mock YouTube having different tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["ai", "ml"]}}]
    }

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
    assert "ai" not in tags_after_dry_run
    assert "ml" not in tags_after_dry_run


def test_update_youtube_tags_skips_when_no_changes(mock_youtube_api):
    """Test that videos are skipped when tags are already in sync"""
    website = WebsiteFactory.create(name="test-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_no_changes",
    )
    WebsiteContentFactory.create(
        website=website,
        title="Video Already Synced",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_no_changes",
                "video_tags": "python, django",
            },
        },
    )

    # Mock YouTube having exactly the same tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["python", "django"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should skip update when tags are identical
    mock_youtube_api.update_video_tags.assert_not_called()


def test_update_youtube_tags_merges_youtube_priority(mock_youtube_api):
    """Test that YouTube tags take priority in ordering when merging"""
    website = WebsiteFactory.create(name="test-course")
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_merge_test",
    )
    content = WebsiteContentFactory.create(
        website=website,
        title="Video Merge Test",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_merge_test",
                "video_tags": "tag1, tag2, tag3",
            },
        },
    )

    # Mock YouTube having different tags, some overlap
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["yt-tag1", "tag2", "yt-tag2"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should merge all tags and sort alphabetically
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_merge_test", "tag1, tag2, tag3, yt-tag1, yt-tag2"
    )

    # Verify merged tags saved to DB
    content.refresh_from_db()
    updated_tags = content.metadata["video_metadata"]["video_tags"]
    assert updated_tags == "tag1, tag2, tag3, yt-tag1, yt-tag2"


def test_update_youtube_tags_handles_poorly_formatted_youtube_tags(mock_youtube_api):
    """Test handling of YouTube tags that contain commas (poorly formatted)"""
    starter = WebsiteStarterFactory.create(config=COURSE_STARTER_CONFIG)
    website = WebsiteFactory.create(
        name="test-course",
        url_path="courses/test-course",
        starter=starter,
    )
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_comma_test",
    )
    content = WebsiteContentFactory.create(
        website=website,
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_comma_test",
                "video_tags": "proper-tag1, proper-tag2",
            },
        },
    )

    # Mock YouTube returning a single tag that contains commas (poorly formatted)
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [
            {"snippet": {"tags": ["game design, critique, game theory, discussion"]}}
        ]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # Should split the poorly formatted tag and merge with DB tags
    # All individual parts should be present and sorted alphabetically
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "yt_comma_test",
        "critique, discussion, game design, game theory, proper-tag1, proper-tag2",
    )

    # Verify merged tags saved to DB
    content.refresh_from_db()
    updated_tags = content.metadata["video_metadata"]["video_tags"]
    assert "critique" in updated_tags
    assert "game design" in updated_tags
    assert "proper-tag1" in updated_tags
    # Verify exact final DB state: all tags properly split, normalized, sorted
    assert (
        updated_tags
        == "critique, discussion, game design, game theory, proper-tag1, proper-tag2"
    )


def test_update_youtube_tags_saves_to_db_even_when_skipping(mock_youtube_api):
    """Test that merged tags are saved to DB even when YouTube update skipped (normal mode only)"""
    starter = WebsiteStarterFactory.create(config=COURSE_STARTER_CONFIG)
    website = WebsiteFactory.create(
        name="test-course",
        url_path="courses/test-course",
        starter=starter,
    )
    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="yt_skip_test",
    )
    content = WebsiteContentFactory.create(
        website=website,
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "yt_skip_test",
                "video_tags": "python",  # DB has only python
            },
        },
    )

    # Mock YouTube already having both tags (python + django)
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["python", "django"]}}]
    }

    call_command(
        "update_youtube_tags",
        filter="test-course",
    )

    # YouTube update should be skipped since merged tags match YouTube tags
    mock_youtube_api.update_video_tags.assert_not_called()

    # Merged tags should still be saved to DB in normal mode (not dry-run)
    content.refresh_from_db()
    updated_tags = content.metadata["video_metadata"]["video_tags"]
    assert updated_tags == "django, python"  # DB should now have both tags


def test_update_youtube_tags_csv_export(mock_youtube_api, tmp_path):
    """Test CSV export functionality with --out parameter"""
    website = WebsiteFactory.create(
        name="test-course",
        short_id="Course-123",
        publish_date=datetime(2023, 1, 1, tzinfo=UTC),
        metadata={"resourcetype": "Course"},
    )

    video = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=video,
        destination=DESTINATION_YOUTUBE,
        destination_id="youtube_id_1",
    )

    content = WebsiteContentFactory.create(
        website=website,
        type="resource",
        markdown="",
        title="Test Video",
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": "youtube_id_1",
                "video_tags": "existing-db-tag",  # Initial DB tags
            },
        },
    )

    # Mock YouTube returning different tags
    mock_youtube_api.client.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"tags": ["youtube-tag", "common-tag"]}}]
    }

    csv_file = tmp_path / "test_output.csv"

    call_command(
        "update_youtube_tags",
        filter="test-course",
        output_file=str(csv_file),
    )

    # Verify CSV file was created and contains correct data
    assert csv_file.exists()

    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]

    # Verify all required columns are present
    assert "vid_resource_id" in row
    assert "existing_yt_tags" in row
    assert "existing_db_tags" in row
    assert "final_tags_yt" in row
    assert "final_tags_db" in row

    # Verify content
    assert row["vid_resource_id"] == str(content.id)
    assert row["existing_yt_tags"] == "youtube-tag, common-tag"
    assert row["existing_db_tags"] == "existing-db-tag"
    # Final tags should be merged (common-tag, existing-db-tag, youtube-tag)
    assert "common-tag" in row["final_tags_yt"]
    assert "existing-db-tag" in row["final_tags_yt"]
    assert "youtube-tag" in row["final_tags_yt"]
    # Verify exact final tags: normalized, sorted alphabetically
    assert row["final_tags_yt"] == "common-tag, existing-db-tag, youtube-tag"
    assert row["final_tags_db"] == "common-tag, existing-db-tag, youtube-tag"

    # Verify YouTube API was called with correct merged tags
    mock_youtube_api.update_video_tags.assert_called_once_with(
        "youtube_id_1", "common-tag, existing-db-tag, youtube-tag"
    )

    # Verify final tags actually saved to database
    content.refresh_from_db()
    final_db_tags = content.metadata["video_metadata"]["video_tags"]
    assert final_db_tags == "common-tag, existing-db-tag, youtube-tag"


def test_flatten_tags_basic():
    """Test flatten_tags with simple list of tags"""
    command = Command()
    tags = ["Python", "Django", "AI"]
    result = command.flatten_tags(tags)

    assert result == {"python", "django", "ai"}


def test_flatten_tags_with_commas():
    """Test flatten_tags handles poorly formatted tags containing commas"""
    command = Command()
    tags = ["Python", "Django, AI", "Machine Learning"]
    result = command.flatten_tags(tags)

    # Should split the "Django, AI" tag and normalize all
    assert result == {"python", "django", "ai", "machine learning"}


def test_flatten_tags_with_whitespace():
    """Test flatten_tags strips whitespace from tags"""
    command = Command()
    tags = ["  Python  ", "  Django  ", "AI"]
    result = command.flatten_tags(tags)

    assert result == {"python", "django", "ai"}


def test_flatten_tags_with_whitespace_and_commas():
    """Test flatten_tags handles tags with both whitespace and commas"""
    command = Command()
    tags = ["Python", "  Django , AI  ", "  Machine Learning  "]
    result = command.flatten_tags(tags)

    # Should split comma-separated tags and strip all whitespace
    assert result == {"python", "django", "ai", "machine learning"}


def test_flatten_tags_removes_empty_strings():
    """Test flatten_tags removes empty strings"""
    command = Command()
    tags = ["Python", "", "  ", "Django"]
    result = command.flatten_tags(tags)

    # Empty strings should be filtered out
    assert result == {"python", "django"}


def test_flatten_tags_with_duplicates():
    """Test flatten_tags handles duplicates (case-insensitive)"""
    command = Command()
    tags = ["Python", "PYTHON", "python", "Django"]
    result = command.flatten_tags(tags)

    # Duplicates should be removed (case-insensitive)
    assert result == {"python", "django"}


def test_flatten_tags_mixed_case_duplicates_with_commas():
    """Test flatten_tags handles complex case with duplicates, commas, and mixed case"""
    command = Command()
    tags = ["Python, PYTHON", "django", "Django, AI", "ai"]
    result = command.flatten_tags(tags)

    # Should handle all edge cases: split commas, normalize case, remove duplicates
    assert result == {"python", "django", "ai"}


def test_flatten_tags_empty_list():
    """Test flatten_tags with empty list"""
    command = Command()
    tags = []
    result = command.flatten_tags(tags)

    assert result == set()
