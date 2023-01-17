""" Syncing API """
import logging
from datetime import datetime
from time import sleep
from typing import List, Optional

import pytz
from django.conf import settings
from django.utils.module_loading import import_string
from mitol.common.utils import now_in_utc

from content_sync import tasks
from content_sync.backends.base import BaseSyncBackend
from content_sync.backends.github import GithubBackend
from content_sync.constants import VERSION_DRAFT
from content_sync.decorators import is_publish_pipeline_enabled, is_sync_enabled
from content_sync.models import ContentSyncState
from content_sync.pipelines.base import BasePipeline
from websites.constants import PUBLISH_STATUS_ERRORED, PUBLISH_STATUS_NOT_STARTED
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


@is_publish_pipeline_enabled
def get_pipeline_api() -> BasePipeline:
    """ Get the base backend pipeline """
    return import_string(
        f"content_sync.pipelines.{settings.CONTENT_SYNC_PIPELINE_BACKEND}.PipelineApi"
    )()


@is_publish_pipeline_enabled
def get_site_pipeline(website: Website, api: Optional[object] = None) -> BasePipeline:
    """ Get the configured sync publishing pipeline """
    return import_string(
        f"content_sync.pipelines.{settings.CONTENT_SYNC_PIPELINE_BACKEND}.SitePipeline"
    )(website, api=api)


@is_publish_pipeline_enabled
def get_theme_assets_pipeline(
    themes_branch: Optional[str] = None, api: Optional[object] = None
) -> BasePipeline:
    """ Get the configured theme asset pipeline """
    return import_string(
        f"content_sync.pipelines.{settings.CONTENT_SYNC_PIPELINE_BACKEND}.ThemeAssetsPipeline"
    )(themes_branch=themes_branch, api=api)


@is_publish_pipeline_enabled
def get_mass_build_sites_pipeline(  # pylint:disable=too-many-arguments
    version: str,
    api: Optional[object] = None,
    prefix: Optional[str] = None,
    themes_branch: Optional[str] = None,
    projects_branch: Optional[str] = None,
    starter: Optional[str] = None,
    offline: Optional[bool] = None,
) -> object:
    """Get the mass build sites pipeline if the backend has one"""
    return import_string(
        f"content_sync.pipelines.{settings.CONTENT_SYNC_PIPELINE_BACKEND}.MassBuildSitesPipeline"
    )(
        version,
        api=api,
        prefix=prefix,
        themes_branch=themes_branch,
        projects_branch=projects_branch,
        starter=starter,
        offline=offline,
    )


@is_publish_pipeline_enabled
def get_unpublished_removal_pipeline(api: Optional[object] = None) -> object:
    """Get the unpublished sites removal pipeline if the backend has one"""
    return import_string(
        f"content_sync.pipelines.{settings.CONTENT_SYNC_PIPELINE_BACKEND}.UnpublishedSiteRemovalPipeline"
    )(api=api)


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
def trigger_publish(website_name: str, version: str):
    """ Publish the website on the backend"""
    if version == VERSION_DRAFT:
        tasks.publish_website_backend_draft.delay(website_name)
    else:
        tasks.publish_website_backend_live.delay(website_name)


@is_sync_enabled
def trigger_unpublished_removal(website: Website):
    """Remove unpublished sites on the backend"""
    tasks.trigger_unpublished_removal.delay(website.name)


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
    trigger_pipeline: Optional[bool] = True,
):
    """Publish a live or draft version of a website"""
    try:
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

        if trigger_pipeline and settings.CONTENT_SYNC_PIPELINE_BACKEND:
            pipeline = get_site_pipeline(website, api=pipeline_api)
            # Always upsert pipeline in case the site url path changed,
            # unless it's been published to production (url path permanent).
            if not website.publish_date:
                pipeline.upsert_pipeline()
            pipeline.unpause_pipeline(version)
            build_id = pipeline.trigger_pipeline_build(version)
            update_kwargs = {
                f"latest_build_id_{version}": build_id,
            }
        else:
            update_kwargs = {}
        # Need to update additional fields
        update_kwargs = {
            f"{version}_publish_status": PUBLISH_STATUS_NOT_STARTED,
            f"{version}_publish_status_updated_on": now_in_utc(),
            f"has_unpublished_{version}": False,
            **update_kwargs,
        }
    except:  # pylint:disable=bare-except
        update_kwargs = {
            f"{version}_publish_status": PUBLISH_STATUS_ERRORED,
            f"{version}_publish_status_updated_on": now_in_utc(),
            f"has_unpublished_{version}": True,
        }
        raise
    finally:
        Website.objects.filter(name=name).update(**update_kwargs)


def throttle_git_backend_calls(backend: object, min_delay: Optional[int] = None):
    """If the current git api limit is too low, sleep until it is reset"""
    min_delay = min_delay or settings.GITHUB_RATE_LIMIT_MIN_SLEEP
    if settings.GITHUB_RATE_LIMIT_CHECK and isinstance(backend, GithubBackend):
        requests_remaining, limit = backend.api.git.rate_limiting
        reset_time = datetime.fromtimestamp(
            backend.api.git.rate_limiting_resettime, tz=pytz.utc
        )
        log.debug(
            "Remaining github calls : %d/%d, reset: %s",
            requests_remaining,
            limit,
            reset_time.isoformat(),
        )
        if requests_remaining <= settings.GITHUB_RATE_LIMIT_CUTOFF:
            sleep((reset_time - now_in_utc()).seconds)
        else:
            # Always wait x seconds between git backend calls
            sleep(min_delay)
