""" Content sync tasks """
import logging
from time import sleep
from typing import List, Optional

import celery
from dateutil.parser import parse
from django.conf import settings
from django.db.models import F, Q
from django.utils.module_loading import import_string
from github.GithubException import RateLimitExceededException
from mitol.common.utils import chunks, now_in_utc, pytz

from content_sync import api
from content_sync.apis import github
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.decorators import single_website_task
from content_sync.models import ContentSyncState
from content_sync.pipelines.base import BaseSyncPipeline
from main.celery import app
from websites.api import mail_on_publish, reset_publishing_fields
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
def sync_unsynced_websites(create_backends: bool = False, check_limit: bool = False):
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
                reset_publishing_fields(website_name)
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


@app.task(acks_late=True)
def upsert_website_pipeline_batch(
    website_names: List[str], create_backend=False, unpause=False
):
    """ Create/update publishing pipelines for multiple websites"""
    api_instance = None
    for website_name in website_names:
        website = Website.objects.get(name=website_name)
        if create_backend:
            backend = api.get_sync_backend(website)
            backend.create_website_in_backend()
            backend.sync_all_content_to_backend()
        pipeline = api.get_sync_pipeline(website, api=api_instance)
        if not api_instance:
            # Keep using the same api instance to minimize multiple authentication calls
            api_instance = pipeline.api
        pipeline.upsert_website_pipeline()
        if unpause:
            for version in [
                BaseSyncPipeline.VERSION_LIVE,
                BaseSyncPipeline.VERSION_DRAFT,
            ]:
                pipeline.unpause_pipeline(version)
    return True


@app.task(bind=True)
def upsert_pipelines(
    self, website_names: List[str], chunk_size=500, create_backend=False, unpause=False
):
    """ Chunk and group batches of pipeline upserts for a specified list of websites"""
    tasks = []
    for website_subset in chunks(
        sorted(website_names),
        chunk_size=chunk_size,
    ):
        tasks.append(
            upsert_website_pipeline_batch.s(
                website_subset, create_backend=create_backend, unpause=unpause
            )
        )
    raise self.replace(celery.group(tasks))


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
def publish_website_backend_draft(website_name: str):
    """
    Create a new backend preview for the website.
    """
    try:
        api.publish_website(website_name, VERSION_DRAFT)
        return True
    except:  # pylint:disable=bare-except
        log.exception("Error publishing draft site %s", website_name)
        return website_name


@app.task(acks_late=True, autoretry_for=(BlockingIOError,), retry_backoff=True)
@single_website_task(10)
def publish_website_backend_live(website_name: str):
    """
    Create a new backend release for the website.
    """
    try:
        api.publish_website(
            website_name,
            VERSION_LIVE,
        )
        return True
    except:  # pylint:disable=bare-except
        log.exception("Error publishing live site %s", website_name)
        return website_name


@app.task()
def publish_website_batch(
    website_names: List[str], version: str, prepublish: Optional[bool] = False
) -> bool:
    """ Call api.publish_website for a batch of websites"""
    result = True
    pipeline_api = import_string(settings.CONTENT_SYNC_PIPELINE).get_api()
    for name in website_names:
        try:
            api.publish_website(
                name,
                version,
                pipeline_api=pipeline_api,
                prepublish=prepublish,
            )
        except:  # pylint:disable=bare-except
            log.exception("Error publishing %s website %s", version, name)
            result = False
    return result


@app.task(bind=True, acks_late=True)
def publish_websites(
    self,
    website_names: List[str],
    version: str,
    chunk_size: Optional[int] = 500,
    prepublish: Optional[bool] = False,
):
    """Publish live or draft versions of multiple websites in parallel batches"""
    if not settings.CONTENT_SYNC_BACKEND or not settings.CONTENT_SYNC_PIPELINE:
        return

    tasks = [
        publish_website_batch.s(name_subset, version, prepublish=prepublish)
        for name_subset in chunks(sorted(website_names), chunk_size=chunk_size)
    ]
    raise self.replace(celery.group(tasks))


@app.task(acks_late=True)
def sync_github_site_configs(url: str, files: List[str], commit: Optional[str] = None):
    """
    Sync WebsiteStarter objects from github
    """
    github.sync_starter_configs(url, files, commit=commit)


def _update_website_status(website_name, version, status, update_time):
    """Update some status fields in Website"""
    if version == VERSION_DRAFT:
        update_kwargs = {
            "draft_publish_status": status,
            "draft_publish_status_updated_on": update_time,
        }
        if status in [
            PUBLISH_STATUS_SUCCEEDED,
            PUBLISH_STATUS_ERRORED,
            PUBLISH_STATUS_ABORTED,
        ]:
            update_kwargs["draft_publish_date"] = update_time

            if status != PUBLISH_STATUS_SUCCEEDED:
                # Allow user to retry
                update_kwargs["has_unpublished_draft"] = True
    else:
        update_kwargs = {
            "live_publish_status": status,
            "live_publish_status_updated_on": update_time,
        }
        if status in [
            PUBLISH_STATUS_SUCCEEDED,
            PUBLISH_STATUS_ERRORED,
            PUBLISH_STATUS_ABORTED,
        ]:
            update_kwargs["publish_date"] = update_time

            if status != PUBLISH_STATUS_SUCCEEDED:
                # Allow user to retry
                update_kwargs["has_unpublished_live"] = True

    Website.objects.filter(name=website_name).update(**update_kwargs)


@app.task(acks_late=True)
def poll_build_status_until_complete(
    website_name: str, version: str, datetime_to_expire: str, user_id: int
):
    """
    Poll concourses REST API repeatedly until the build completes
    """
    now = now_in_utc()
    try:
        website = Website.objects.get(name=website_name)
        build_id = (
            website.latest_build_id_draft
            if version == VERSION_DRAFT
            else website.latest_build_id_live
        )
        if build_id is not None:
            pipeline = api.get_sync_pipeline(website)
            status = pipeline.get_build_status(build_id)
            _update_website_status(website_name, version, status, now)

            if status in [
                PUBLISH_STATUS_SUCCEEDED,
                PUBLISH_STATUS_ERRORED,
                PUBLISH_STATUS_ABORTED,
            ]:
                mail_on_publish(
                    website_name, version, status == PUBLISH_STATUS_SUCCEEDED, user_id
                )
                return
    except:  # pylint: disable=bare-except
        log.exception(
            "Error running poll_build_status_until_complete for website %s, version %s",
            website_name,
            version,
        )

    if now < parse(datetime_to_expire):
        # if not past expiration date, check again in 10 seconds
        poll_build_status_until_complete.apply_async(
            args=[website_name, version, datetime_to_expire, user_id],
            countdown=settings.WEBSITE_POLL_FREQUENCY,
        )
    else:
        # if past the expiration date, assume something went wrong
        mail_on_publish(website_name, version, False, user_id)
        _update_website_status(website_name, version, PUBLISH_STATUS_ERRORED, now)
