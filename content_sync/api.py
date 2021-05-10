""" Syncing API """
import logging

from django.conf import settings
from django.utils.module_loading import import_string

from content_sync import tasks
from content_sync.backends.base import BaseSyncBackend
from content_sync.decorators import is_sync_enabled
from content_sync.models import ContentSyncState
from websites.models import Website, WebsiteContent


log = logging.getLogger()


def upsert_content_sync_state(content: WebsiteContent):
    """ Create or update the content sync state """
    ContentSyncState.objects.update_or_create(
        content=content, defaults=dict(current_checksum=content.calculate_checksum())
    )


def get_sync_backend(website: Website) -> BaseSyncBackend:
    """ Get the configured sync backend """
    return import_string(settings.CONTENT_SYNC_BACKEND)(website)


@is_sync_enabled
def sync_content(sync_state: ContentSyncState):
    """ Sync a piece of content based on its sync state """
    backend = get_sync_backend(sync_state.content.website)
    backend.sync_content_to_backend(sync_state)


@is_sync_enabled
def create_website_backend(website: Website):
    """ Create the backend for a website"""
    tasks.create_website_backend.delay(website.name)


@is_sync_enabled
def update_website_backend(website: Website):
    """ Update the backend content for a website"""
    tasks.sync_website_content.delay(website.name)


@is_sync_enabled
def preview_website(website: Website):
    """ Create a preview for the website on the backend"""
    tasks.preview_website_backend.delay(website.name)


@is_sync_enabled
def publish_website(website: Website):
    """ Publish the website on the backend"""
    tasks.publish_website_backend.delay(website.name)
