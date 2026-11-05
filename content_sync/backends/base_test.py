"""Tests for base backend implementation"""

from typing import TYPE_CHECKING, Any

import pytest

from content_sync.backends.base import BaseSyncBackend
from content_sync.factories import ContentSyncStateFactory
from websites.factories import WebsiteFactory
from websites.models import WebsiteContent

if TYPE_CHECKING:
    from content_sync.models import ContentSyncState
    from users.models import User


class _ImplementedBackend(BaseSyncBackend):
    """Not implemented"""

    def backend_exists(self): ...

    def create_website_in_backend(self): ...

    def merge_backend_draft(self): ...

    def merge_backend_live(self): ...

    def create_content_in_backend(self, sync_state: ContentSyncState): ...

    def update_content_in_backend(self, sync_state: ContentSyncState): ...

    def delete_content_in_backend(self, sync_state: ContentSyncState): ...

    def create_content_in_db(self, data: Any): ...

    def update_content_in_db(self, data: Any): ...

    def delete_content_in_db(self, data: Any): ...

    def sync_all_content_to_db(
        self, ref: str | None = None, path: str | None = None
    ): ...

    def delete_orphaned_content_in_backend(
        self, *, commit_user: User | None = None
    ): ...


class _NotImplementedBackend(BaseSyncBackend):
    """Not implemented"""


def test_base_sync_backend_subclass_implemented(mocker):
    """Verify BaseSyncBackend doesn't unimplemented subclasses"""
    # no errors
    _ImplementedBackend(mocker.Mock())


def test_base_sync_backend_subclass_not_implemented(mocker):
    """Verify BaseSyncBackend doesn't unimplemented subclasses"""
    with pytest.raises(TypeError):
        _NotImplementedBackend(  # pylint: disable=abstract-class-instantiated
            mocker.Mock()
        )


def test_sync_content_to_backend_create(mocker):
    """Verify that sync_content_to_backend calls the create method based on the state"""
    mock_create_content_in_backend = mocker.patch.object(
        _ImplementedBackend, "create_content_in_backend", return_value=None
    )
    state = mocker.Mock(synced_checksum=None)
    state.content.deleted = None

    backend = _ImplementedBackend(mocker.Mock())
    backend.sync_content_to_backend(state)
    mock_create_content_in_backend.assert_called_once_with(state)


def test_sync_content_to_backend_update(mocker):
    """Verify that sync_content_to_backend calls the update method based on the state"""
    mock_update_content_in_backend = mocker.patch.object(
        _ImplementedBackend, "update_content_in_backend", return_value=None
    )
    state = mocker.Mock(synced_checksum="abc")
    state.content.deleted = None

    backend = _ImplementedBackend(mocker.Mock())
    backend.sync_content_to_backend(state)
    mock_update_content_in_backend.assert_called_once_with(state)


def test_sync_content_to_backend_delete(mocker):
    """Verify that sync_content_to_backend calls the delete method based on the state"""
    mock_delete_content_in_backend = mocker.patch.object(
        _ImplementedBackend, "delete_content_in_backend", return_value=None
    )
    state = mocker.Mock(synced_checksum="abc")
    state.content.deleted = True

    backend = _ImplementedBackend(mocker.Mock())
    backend.sync_content_to_backend(state)
    mock_delete_content_in_backend.assert_called_once_with(state)


@pytest.mark.django_db
def test_sync_all_content_to_backend(mocker):
    """Verify that sync_all_content_to_backend calls sync_content_to_backend for each piece of content"""
    mock_sync_content_to_backend = mocker.patch.object(
        _ImplementedBackend, "sync_content_to_backend", return_value=None
    )
    website = WebsiteFactory.create()
    states = ContentSyncStateFactory.create_batch(5, content__website=website)
    backend = _ImplementedBackend(website)
    backend.sync_all_content_to_backend()
    assert mock_sync_content_to_backend.call_count == len(states)
    for state in states:
        mock_sync_content_to_backend.assert_any_call(state)


def test_sync_all_content_rejects_unsupported_commit_user(mocker):
    """The default implementation must not silently ignore an explicit actor."""
    backend = _ImplementedBackend(mocker.Mock())
    sync_content = mocker.patch.object(backend, "sync_content_to_backend")

    with pytest.raises(NotImplementedError, match="overriding the commit user"):
        backend.sync_all_content_to_backend(commit_user=mocker.Mock())

    sync_content.assert_not_called()


@pytest.mark.django_db
def test_sync_all_content_preserves_empty_scope(mocker):
    """An empty explicit queryset must not sync other content in the website."""
    website = WebsiteFactory.create()
    ContentSyncStateFactory.create(content__website=website)
    backend = _ImplementedBackend(website)
    sync_content = mocker.patch.object(backend, "sync_content_to_backend")

    backend.sync_all_content_to_backend(query_set=WebsiteContent.objects.none())

    sync_content.assert_not_called()
