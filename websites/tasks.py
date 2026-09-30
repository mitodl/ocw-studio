"""Celery tasks for the websites app."""

import logging
import time

import celery
from django.conf import settings
from github.GithubException import RateLimitExceededException

from content_sync import api
from content_sync.backends.github import GithubBackend
from content_sync.tasks import sync_website_content
from main.celery import app
from websites.management.commands import remove_uuid_from_filenames as uuid_renames
from websites.models import Website

log = logging.getLogger(__name__)

# Redis redelivers a task that is not acknowledged within its 1-hour
# visibility timeout, even one only waiting on a countdown. Waits stay well
# inside it.
SYNC_WAIT_CAP_SECONDS = 1800
SYNC_LOCK_RETRY_SECONDS = 60


def _git_rate_limit_wait(website):
    """
    Return the seconds to wait before syncing *website*, or 0 to go now.

    Mirrors api.throttle_git_backend_calls, which sleeps instead. A sleep
    that long inside a task could outlast the visibility timeout.
    """
    if not settings.GITHUB_RATE_LIMIT_CHECK:
        return 0
    backend = api.get_sync_backend(website)
    if not isinstance(backend, GithubBackend):
        return 0
    remaining, _ = backend.api.git.rate_limiting
    if remaining > settings.GITHUB_RATE_LIMIT_CUTOFF:
        return 0
    return max(1, int(backend.api.git.rate_limiting_resettime - time.time()))


def _requeue(website_names, seconds):
    """Run the sync again for the same websites after *seconds*, capped."""
    sync_renamed_websites.apply_async(
        (website_names,), countdown=min(seconds, SYNC_WAIT_CAP_SECONDS)
    )


@app.task(acks_late=True, reject_on_worker_lost=True)
def sync_renamed_websites(website_names):
    """
    Sync the first of *website_names* to the backend, then queue the rest.

    One website per run keeps each run short, so a killed run is requeued
    and resumes with the websites still left. Only these websites are
    synced, and publish status is not reset, which is why this does not
    reuse sync_unsynced_websites. Never raises: a failing site is logged and
    the rest continue.
    """
    if not website_names:
        return
    name, rest = website_names[0], list(website_names[1:])
    website = Website.objects.filter(name=name).first()
    if website is not None:
        try:
            wait = _git_rate_limit_wait(website)
            if wait:
                log.info("GitHub rate limit is low, will sync %s later", name)
                _requeue(website_names, wait)
                return
            # Called directly, not queued, so it runs here and still takes
            # sync_website_content's per-site lock.
            sync_website_content(name)
        except BlockingIOError:
            log.info("A sync of %s is already running, will retry", name)
            _requeue(website_names, SYNC_LOCK_RETRY_SECONDS)
            return
        except RateLimitExceededException:
            log.warning("GitHub rate limit hit while syncing %s, will retry", name)
            _requeue(website_names, SYNC_WAIT_CAP_SECONDS)
            return
        except Exception:
            log.exception("Failed to sync %s after the UUID rename", name)
    if rest:
        sync_renamed_websites.delay(rest)


@app.task(acks_late=True, reject_on_worker_lost=True)
def rename_uuid_files(website_ids, chunk_size, *, skip_sync):
    """
    Plan the UUID rename and hand the work to a chord of chunk tasks.

    Nothing is written before the hand-off, so a redelivery starts over.
    *website_ids* is None for every website.
    """
    chunks, skipped = uuid_renames.plan_job(website_ids, chunk_size)
    if not chunks:
        return finish_uuid_rename.delay([], skipped=skipped, skip_sync=skip_sync).id
    header = [
        rename_uuid_files_chunk.si(index, *chunk) for index, chunk in enumerate(chunks)
    ]
    callback = finish_uuid_rename.s(skipped=skipped, skip_sync=skip_sync)
    return celery.chord(header)(callback).id


@app.task(acks_late=True, reject_on_worker_lost=True)
def rename_uuid_files_chunk(chunk_id, assignments, content_pks, website_ids):
    """Rename and patch one chunk. Never raises, see run_chunk."""
    return uuid_renames.run_chunk(chunk_id, assignments, content_pks, website_ids)


@app.task(acks_late=True, reject_on_worker_lost=True)
def finish_uuid_rename(summaries, *, skipped, skip_sync):
    """Log the job's final summary, then start syncing the renamed websites."""
    websites, _ = uuid_renames.finish_job(summaries, skipped)
    if websites and not skip_sync and settings.CONTENT_SYNC_BACKEND:
        sync_renamed_websites.delay(websites)
    return websites
