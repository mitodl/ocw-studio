""" Syncing API """
import logging
from typing import List, Optional

from django.conf import settings
from django.utils.module_loading import import_string

from content_sync import tasks
from content_sync.backends.base import BaseSyncBackend
from content_sync.decorators import is_publish_pipeline_enabled, is_sync_enabled
from content_sync.models import ContentSyncState
from content_sync.pipelines.base import BaseSyncPipeline
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


def get_sync_pipeline(website: Website) -> BaseSyncPipeline:
    """ Get the configured sync publishing pipeline """
    return import_string(settings.CONTENT_SYNC_PIPELINE)(website)


@is_sync_enabled
def sync_content(sync_state: ContentSyncState):
    """ Sync a piece of content based on its sync state """
    backend = get_sync_backend(sync_state.content.website)
    backend.sync_content_to_backend(sync_state)


@is_sync_enabled
def create_website_backend(website: Website):
    """ Create the backend for a website"""
    tasks.create_website_backend.delay(website.name)


@is_publish_pipeline_enabled
def create_website_publishing_pipeline(website: Website):
    """ Create the publish pipeline for a website"""
    tasks.upsert_website_publishing_pipeline.delay(website.name)


@is_publish_pipeline_enabled
def unpause_publishing_pipeline(website: Website, version: str):
    """Unpause the publishing pipeline"""
    pipeline = get_sync_pipeline(website)
    pipeline.unpause_pipeline(version)


@is_sync_enabled
def update_website_backend(website: Website):
    """ Update the backend content for a website"""
    tasks.sync_website_content.delay(website.name)


@is_sync_enabled
def preview_website(website: Website):
    """ Create a preview for the website on the backend"""
    tasks.preview_website_backend.delay(website.name, website.draft_publish_date)


@is_sync_enabled
def publish_website(website: Website):
    """ Publish the website on the backend"""
    tasks.publish_website_backend.delay(website.name, website.publish_date)


def sync_github_website_starters(
    url: str, files: List[str], commit: Optional[str] = None
):
    """ Sync website starters from github """
    tasks.sync_github_site_configs.delay(url, files, commit=commit)
