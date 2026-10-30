"""Tests for signals"""

import pytest
from safedelete.models import HARD_DELETE

from content_sync.apis.github import GIT_DATA_FILEPATH
from users.factories import UserFactory
from websites import constants
from websites.api import sync_website_content_references
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent
from websites.serializers import WebsiteContentDetailSerializer


@pytest.mark.django_db
def test_handle_website_save():
    """Groups should be created for a new Website"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    assert website.admin_group is not None
    assert website.editor_group is not None
    assert website.owner.has_perm(constants.PERMISSION_EDIT, website)


@pytest.mark.django_db
def test_navmenu_updated_on_page_title_change(mocker, enable_websitecontent_signal):
    """Navmenu pageRef and name are updated when a page's title changes"""
    website = WebsiteFactory.create(owner=UserFactory.create())

    page = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_PAGE,
        dirpath="",
        title="Original Title",
        filename="original-title",
        text_id="abc123",
    )
    navmenu = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_NAVMENU,
        metadata={
            constants.WEBSITE_CONTENT_LEFTNAV: [
                {
                    "identifier": "abc123",
                    "pageRef": "/pages/original-title",
                    "name": "Original Title",
                }
            ]
        },
    )

    page.title = "New Title"
    serializer = WebsiteContentDetailSerializer(
        instance=page, data={"title": "New Title"}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    navmenu.refresh_from_db()
    menu_item = navmenu.metadata[constants.WEBSITE_CONTENT_LEFTNAV][0]
    assert menu_item["pageRef"] == "/pages/new-title"
    assert menu_item["name"] == "New Title"


@pytest.mark.django_db
def test_deleting_linked_resource_unlinks_it_from_video():
    """Soft-deleting a linked caption resource removes it from the video's relation content."""
    website = WebsiteFactory.create()
    captions = WebsiteContentFactory.create(
        website=website,
        filename="lecture01_captions_vtt",
        file=f"courses/{website.name}/lecture01_captions.vtt",
    )
    video = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_files": {
                "video_captions_resources": {
                    "content": [str(captions.text_id)],
                    "website": website.name,
                }
            },
        },
        filename="lecture01_mp4",
    )
    sync_website_content_references(video)

    captions.delete()

    video.refresh_from_db()
    assert video.metadata["video_files"]["video_captions_resources"]["content"] == []


@pytest.mark.django_db
def test_hard_delete_enqueues_cleanup_with_last_synced_path(
    settings, mocker, django_capture_on_commit_callbacks
):
    """Hard-deleting content enqueues backend cleanup using its last-synced path"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_task = mocker.patch("websites.signals.delete_orphaned_content_file")
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)
    content.content_sync_state.data = {GIT_DATA_FILEPATH: "path/to/synced-file.md"}
    content.content_sync_state.save()
    website_pk = content.website.pk
    updated_by_id = content.updated_by_id

    with django_capture_on_commit_callbacks(execute=True):
        content.delete(force_policy=HARD_DELETE)

    mock_task.delay.assert_called_once_with(
        str(website_pk), "path/to/synced-file.md", updated_by_id
    )


@pytest.mark.django_db
def test_hard_delete_falls_back_to_computed_path_when_never_synced(
    settings, mocker, django_capture_on_commit_callbacks
):
    """Content with no recorded synced path falls back to a freshly computed one"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_task = mocker.patch("websites.signals.delete_orphaned_content_file")
    mocker.patch(
        "websites.signals.get_destination_filepath",
        return_value="path/to/computed-file.md",
    )
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)
    website_pk = content.website.pk
    updated_by_id = content.updated_by_id

    with django_capture_on_commit_callbacks(execute=True):
        content.delete(force_policy=HARD_DELETE)

    mock_task.delay.assert_called_once_with(
        str(website_pk), "path/to/computed-file.md", updated_by_id
    )


@pytest.mark.django_db
def test_hard_delete_skips_cleanup_when_path_cannot_be_determined(
    settings, mocker, django_capture_on_commit_callbacks
):
    """No task is enqueued when neither a synced path nor a computed one is available"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_task = mocker.patch("websites.signals.delete_orphaned_content_file")
    mocker.patch("websites.signals.get_destination_filepath", return_value=None)
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)

    with django_capture_on_commit_callbacks(execute=True):
        content.delete(force_policy=HARD_DELETE)

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
def test_hard_delete_skips_backend_when_sync_disabled(
    settings, mocker, django_capture_on_commit_callbacks
):
    """No cleanup should be enqueued when CONTENT_SYNC_BACKEND isn't configured"""
    settings.CONTENT_SYNC_BACKEND = ""
    mock_task = mocker.patch("websites.signals.delete_orphaned_content_file")
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)

    with django_capture_on_commit_callbacks(execute=True):
        content.delete(force_policy=HARD_DELETE)

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
def test_soft_delete_does_not_touch_backend(
    settings, mocker, django_capture_on_commit_callbacks
):
    """A regular (soft) delete should not trigger the hard-delete backend cleanup"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_task = mocker.patch("websites.signals.delete_orphaned_content_file")
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)

    with django_capture_on_commit_callbacks(execute=True):
        content.delete()

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
def test_hard_delete_backend_error_does_not_block_deletion(
    settings, mocker, django_capture_on_commit_callbacks
):
    """A backend failure while cleaning up (end-to-end, task included) is logged, not raised"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mock_get_backend = mocker.patch("content_sync.tasks.api.get_sync_backend")
    mock_get_backend.return_value.api.delete_content_file.side_effect = Exception(
        "backend unavailable"
    )
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)
    content.content_sync_state.data = {GIT_DATA_FILEPATH: "path/to/synced-file.md"}
    content.content_sync_state.save()
    content_id = content.id

    with django_capture_on_commit_callbacks(execute=True):
        content.delete(force_policy=HARD_DELETE)  # must not raise

    assert not WebsiteContent.all_objects.filter(id=content_id).exists()
