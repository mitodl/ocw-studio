""" Content sync tasks """
import logging
from time import sleep
from typing import List, Optional

from dateutil.parser import parse
from django.conf import settings
from django.db.models import F, Q
from django.utils.module_loading import import_string
from github.GithubException import RateLimitExceededException
from mitol.common.utils import now_in_utc, pytz

from content_sync import api
from content_sync.apis import github
from content_sync.decorators import single_website_task
from content_sync.models import ContentSyncState
from content_sync.pipelines.base import BaseSyncPipeline
from main.celery import app
from websites.api import mail_website_admins_on_publish
from websites.constants import (
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_SUCCEEDED,
)
from websites.models import Website


log = logging.getLogger(__name__)


@app.task(acks_late=True)
def sync_content(content_sync_id: str):
    """ Sync a piece of content """
    try:
        sync_state = ContentSyncState.objects.get(id=content_sync_id)
    except ContentSyncState.DoesNotExist:
        log.debug(
            "Attempted to sync ContentSyncState that doesn't exist: id=%s",
            content_sync_id,
        )
    else:
        api.sync_content(sync_state)


@app.task(acks_late=True)
def sync_all_websites(create_backends: bool = False, check_limit: bool = False):
    """
    Sync all websites with unsynced content if they have existing repos.
    This should be rarely called, and only in a management command.
    """
    from content_sync.backends.github import (  # pylint:disable=import-outside-toplevel
        GithubBackend,
    )

    if not settings.CONTENT_SYNC_BACKEND:
        return
    for website_name in (  # pylint:disable=too-many-nested-blocks
        ContentSyncState.objects.exclude(
            Q(current_checksum=F("synced_checksum")) & Q(synced_checksum__isnull=False)
        )
        .values_list("content__website__name", flat=True)
        .distinct()
    ):
        if website_name:
            log.debug("Syncing website %s to backend", website_name)
            try:
                backend = api.get_sync_backend(Website.objects.get(name=website_name))
                if isinstance(backend, GithubBackend):
                    if check_limit:
                        # Check the remaining api calls available; if low, wait til the rate limit resets
                        rate_limit = backend.api.git.get_rate_limit().core
                        log.debug("Remaining github calls %d:", rate_limit.remaining)
                        if rate_limit.remaining <= 100:
                            sleep(
                                (
                                    rate_limit.reset.replace(tzinfo=pytz.utc)
                                    - now_in_utc()
                                ).seconds
                            )
                        else:
                            # wait a bit between websites to avoid using up the hourly API rate limit
                            sleep(5)
                if create_backends or backend.backend_exists():
                    backend.create_website_in_backend()
                    backend.sync_all_content_to_backend()
            except RateLimitExceededException:
                # Too late, can't even check rate limit reset time now so bail
                raise
            except:  # pylint:disable=bare-except
                log.exception("Error syncing website %s", website_name)


@app.task(acks_late=True)
def create_website_backend(website_name: str):
    """ Create a backend for a website """
    try:
        website = Website.objects.get(name=website_name)
    except Website.DoesNotExist:
        log.debug(
            "Attempted to create backend for Website that doesn't exist: name=%s",
            website_name,
        )
    else:
        backend = api.get_sync_backend(website)
        backend.create_website_in_backend()


@app.task(acks_late=True)
def upsert_website_publishing_pipeline(website_name: str):
    """ Create/update a pipeline for previewing & publishing a website """
    try:
        website = Website.objects.get(name=website_name)
    except Website.DoesNotExist:
        log.debug(
            "Attempted to create pipeline for Website that doesn't exist: name=%s",
            website_name,
        )
    else:
        pipeline = api.get_sync_pipeline(website)
        pipeline.upsert_website_pipeline()


@app.task(acks_late=True, autoretry_for=(BlockingIOError,), retry_backoff=True)
@single_website_task(10)
def sync_website_content(website_name: str):
    """ Commit any unsynced files to the backend for a website """
    try:
        website = Website.objects.get(name=website_name)
    except Website.DoesNotExist:
        log.debug(
            "Attempted to update backend for Website that doesn't exist: name=%s",
            website_name,
        )
    else:
        backend = api.get_sync_backend(website)
        backend.sync_all_content_to_backend()


@app.task(acks_late=True, autoretry_for=(BlockingIOError,), retry_backoff=True)
@single_website_task(10)
def preview_website_backend(website_name: str, preview_date: str):
    """
    Create a new backend preview for the website.
    """
    try:
        website = Website.objects.get(name=website_name)
        for action in settings.PREPUBLISH_ACTIONS:
            import_string(action)(website)
        backend = api.get_sync_backend(website)
        backend.sync_all_content_to_backend()
        backend.create_backend_preview()
        if preview_date is None:
            api.unpause_publishing_pipeline(website, BaseSyncPipeline.VERSION_DRAFT)
    except:  # pylint:disable=bare-except
        log.exception("Error previewing site %s", website.name)
        mail_website_admins_on_publish(website, BaseSyncPipeline.VERSION_DRAFT, False)


@app.task(acks_late=True, autoretry_for=(BlockingIOError,), retry_backoff=True)
@single_website_task(10)
def publish_website_backend(website_name: str, publish_date: str):
    """
    Create a new backend release for the website.
    """
    try:
        website = Website.objects.get(name=website_name)
        for action in settings.PREPUBLISH_ACTIONS:
            import_string(action)(website)
        backend = api.get_sync_backend(website)
        backend.sync_all_content_to_backend()
        backend.create_backend_release()
        if publish_date is None:
            api.unpause_publishing_pipeline(website, BaseSyncPipeline.VERSION_LIVE)
    except:  # pylint:disable=bare-except
        log.exception("Error publishing site %s", website.name)
        mail_website_admins_on_publish(website, BaseSyncPipeline.VERSION_LIVE, False)


@app.task(acks_late=True)
def sync_github_site_configs(url: str, files: List[str], commit: Optional[str] = None):
    """
    Sync WebsiteStarter objects from github
    """
    github.sync_starter_configs(url, files, commit=commit)


@app.task(acks_late=True)
def poll_build_status_until_complete(
    website_name: str, version: str, datetime_to_expire: str
):
    """
    Poll concourses REST API repeatedly until the build completes
    """
    pipeline = api.get_sync_pipeline(Website.objects.get(name=website_name))
    status = pipeline.get_latest_build_status(version)
    now = now_in_utc()
    if version == "draft":
        update_kwargs = {
            "draft_publish_status": status,
            "draft_publish_status_updated_on": now,
        }
        if status in [
            PUBLISH_STATUS_SUCCEEDED,
            PUBLISH_STATUS_ERRORED,
            PUBLISH_STATUS_ABORTED,
        ]:
            update_kwargs["draft_publish_date"] = now

            if status != PUBLISH_STATUS_SUCCEEDED:
                # Allow user to retry
                update_kwargs["has_unpublished_draft"] = True
    else:
        update_kwargs = {
            "live_publish_status": status,
            "live_publish_status_updated_on": now,
        }
        if status in [
            PUBLISH_STATUS_SUCCEEDED,
            PUBLISH_STATUS_ERRORED,
            PUBLISH_STATUS_ABORTED,
        ]:
            update_kwargs["publish_date"] = now

            if status != PUBLISH_STATUS_SUCCEEDED:
                # Allow user to retry
                update_kwargs["has_unpublished_live"] = True

    Website.objects.filter(name=website_name).update(**update_kwargs)

    if status in [
        PUBLISH_STATUS_SUCCEEDED,
        PUBLISH_STATUS_ERRORED,
        PUBLISH_STATUS_ABORTED,
    ]:
        return

    if now < parse(datetime_to_expire):
        # if not past expiration date, check again in 10 seconds
        poll_build_status_until_complete.apply_async(
            args=[website_name, version, datetime_to_expire],
            countdown=settings.WEBSITE_POLL_FREQUENCY,
        )
