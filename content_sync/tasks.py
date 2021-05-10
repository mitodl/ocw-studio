""" Content sync tasks """
import logging
from time import sleep

from django.conf import settings
from django.db.models import F, Q
from github.GithubException import RateLimitExceededException
from mitol.common.utils import now_in_utc, pytz

from content_sync import api
from content_sync.decorators import single_website_task
from content_sync.models import ContentSyncState
from main.celery import app
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
def sync_all_websites():
    """
    Sync all websites with unsynced content.  This should be rarely called, and only
    in a management command.
    """
    from content_sync.backends.github import (  # pylint:disable=import-outside-toplevel
        GithubBackend,
    )

    if not settings.CONTENT_SYNC_BACKEND:
        return
    for website_name in (
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
                    # Check the remaining api calls available; if low, wait til the rate limit resets
                    rate_limit = backend.api.git.get_rate_limit().core
                    log.debug("Remaining github calls %d:", rate_limit.remaining)
                    if rate_limit.remaining <= 100:
                        sleep(
                            (
                                rate_limit.reset.replace(tzinfo=pytz.utc) - now_in_utc()
                            ).seconds
                        )
                    else:
                        # wait a bit between websites to avoid using up the hourly API rate limit
                        sleep(5)

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
def preview_website_backend(website_name: str):
    """
    Create a new backend preview for the website.
    """
    backend = api.get_sync_backend(Website.objects.get(name=website_name))
    backend.create_backend_preview()


@app.task(acks_late=True, autoretry_for=(BlockingIOError,), retry_backoff=True)
@single_website_task(10)
def publish_website_backend(website_name: str):
    """
    Create a new backend release for the website.
    """
    backend = api.get_sync_backend(Website.objects.get(name=website_name))
    backend.create_backend_release()
