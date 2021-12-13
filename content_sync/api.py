""" Syncing API """
import logging
from typing import List, Optional

from django.conf import settings
from django.utils.module_loading import import_string
from mitol.common.utils import now_in_utc

from content_sync import tasks
from content_sync.backends.base import BaseSyncBackend
from content_sync.constants import VERSION_DRAFT
from content_sync.decorators import is_publish_pipeline_enabled, is_sync_enabled
from content_sync.models import ContentSyncState
from content_sync.pipelines.base import BaseSyncPipeline
from websites.constants import PUBLISH_STATUS_NOT_STARTED
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


def get_sync_pipeline(
    website: Website, api: Optional[object] = None
) -> BaseSyncPipeline:
    """ Get the configured sync publishing pipeline """
    return import_string(settings.CONTENT_SYNC_PIPELINE)(website, api=api)


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


@is_sync_enabled
def update_website_backend(website: Website):
    """ Update the backend content for a website"""
    tasks.sync_website_content.delay(website.name)


@is_sync_enabled
def trigger_publish(website_name: str, version: str):
    """ Publish the website on the backend"""
    if version == VERSION_DRAFT:
        tasks.publish_website_backend_draft.delay(website_name)
    else:
        tasks.publish_website_backend_live.delay(website_name)


def sync_github_website_starters(
    url: str, files: List[str], commit: Optional[str] = None
):
    """ Sync website starters from github """
    tasks.sync_github_site_configs.delay(url, files, commit=commit)


def publish_website(  # pylint: disable=too-many-arguments
    name: str,
    version: str,
    pipeline_api: Optional[object] = None,
    prepublish: Optional[bool] = True,
):
    """Publish a live or draft version of a website"""
    website = Website.objects.get(name=name)
    if prepublish:
        for action in settings.PREPUBLISH_ACTIONS:
            import_string(action)(website, version=version)
    backend = get_sync_backend(website)
    backend.sync_all_content_to_backend()
    if version == VERSION_DRAFT:
        backend.merge_backend_draft()
    else:
        backend.merge_backend_live()

    pipeline = get_sync_pipeline(website, api=pipeline_api)
    pipeline.unpause_pipeline(version)
    build_id = pipeline.trigger_pipeline_build(version)
    update_kwargs = {
        f"latest_build_id_{version}": build_id,
    }
    if (
        getattr(website, f"{version}_publish_status") != PUBLISH_STATUS_NOT_STARTED
        or getattr(website, f"{version}_publish_status_updated_on") is None
    ):
        # Need to update additional fields
        update_kwargs = {
            f"{version}_publish_status": PUBLISH_STATUS_NOT_STARTED,
            f"{version}_publish_status_updated_on": now_in_utc(),
            f"{version}_last_published_by": None,
            f"has_unpublished_{version}": False,
            **update_kwargs,
        }
    Website.objects.filter(pk=website.pk).update(**update_kwargs)
