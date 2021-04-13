""" Syncing API """
import logging

from django.conf import settings
from django.db import transaction
from django.utils.module_loading import import_string

from content_sync import tasks
from content_sync.backends.base import BaseSyncBackend
from content_sync.models import ContentSyncState
from websites.models import WebsiteContent


log = logging.getLogger()


def upsert_content_sync_state(content: WebsiteContent):
    """ Create the content sync state """
    sync_state, _ = ContentSyncState.objects.update_or_create(
        content=content, defaults=dict(current_checksum=content.calculate_checksum())
    )
    transaction.on_commit(lambda: tasks.sync_content.delay(sync_state.id))


def is_sync_enabled() -> bool:
    """ Returns True if the sync is enabled """
    return getattr(settings, "CONTENT_SYNC_BACKEND", None) is not None


def get_sync_backend() -> BaseSyncBackend:
    """ Get the configured sync backend """
    return import_string(settings.CONTENT_SYNC_BACKEND)


def sync_content(sync_state: ContentSyncState):
    """ Sync a piece of content based on its sync state """
    if not is_sync_enabled():
        log.debug("Syncing is disabled")
        return
    backend = get_sync_backend()
    backend.sync_content_to_backend(sync_state)
