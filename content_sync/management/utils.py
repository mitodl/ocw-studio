"""Helpers for content sync management commands."""  # noqa: INP001

import logging
from contextlib import contextmanager

from django.conf import settings
from django.core.management import CommandError
from django.db import transaction
from mitol.common.utils import now_in_utc

from content_sync.repair import collect_repaired_content
from content_sync.tasks import sync_unsynced_websites
from users.models import User

log = logging.getLogger(__name__)


def get_commit_user(email: str) -> User:
    """Resolve the active Studio user responsible for a manual sync."""
    try:
        return User.objects.get(email=email, is_active=True)
    except User.DoesNotExist as exc:
        msg = "--user must be the email address of an existing active Studio user."
        raise CommandError(msg) from exc


def _run_deferred_tasks(tasks):
    """Wait for the postponed tasks and return the checksums they report."""
    results = {}
    for pk, signature in sorted(tasks.items()):
        try:
            results[pk] = signature.delay()
        except Exception:
            # In eager mode a failing task raises here instead of returning a result.
            log.exception("Could not run the deferred task for content %s", pk)
    checksums = {}
    for pk, result in results.items():
        checksum = result.get(propagate=False)
        if not result.successful():
            log.error("The deferred task for content %s failed: %s", pk, checksum)
        elif checksum is not None:
            checksums[pk] = checksum
    return checksums


@contextmanager
def sync_repaired_content(stdout, *, enabled: bool):
    """Sync committed repairs and the never-synced targets of new references."""
    if not enabled or not settings.CONTENT_SYNC_BACKEND:
        yield None
        return

    with collect_repaired_content() as repair:
        yield repair

    def sync():
        if repair.tasks:
            stdout.write(f"Waiting for {len(repair.tasks)} deferred tasks")
        content_ids = repair.prepare_sync(_run_deferred_tasks(repair.tasks))
        stdout.write(f"Syncing {len(content_ids)} content records")
        start = now_in_utc()
        task = sync_unsynced_websites.delay(
            create_backends=True, content_ids=content_ids
        )
        stdout.write(f"Starting task {task}...")
        task.get()
        total_seconds = (now_in_utc() - start).total_seconds()
        stdout.write(f"Backend sync finished, took {total_seconds} seconds")

    transaction.on_commit(sync, using=repair.connection.alias)
