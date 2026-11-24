"""Track the content writes and new references made by a batch repair."""

from collections import defaultdict
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from functools import partial

from django.db import transaction
from django.db.models import F

from content_sync import api
from content_sync.constants import GIT_DATA_FILEPATH
from content_sync.models import ContentSyncState
from content_sync.utils import get_destination_filepath
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig
from websites.utils import videos_referencing_renamed_files

_active_repair = ContextVar("active_content_repair", default=None)


@dataclass
class _ContentChange:
    original: str | None
    originally_synced: str | None
    current: str


class _RepairScope:
    def __init__(self, connection):
        self.connection = connection
        self.changes = {}
        self.references = set()
        self.url_references = set()
        self.changed_files = {}
        self.tasks = {}

    def record_change(self, content_id, previous, synced, current):
        if content_id in self.changes:
            self.changes[content_id].current = current
        else:
            self.changes[content_id] = _ContentChange(previous, synced, current)

    def record_file_change(self, content_id, previous, current):
        if self.changed_files.setdefault(content_id, previous) == current:
            del self.changed_files[content_id]

    def defer(self, content_id, signature):
        """Postpone a task that returns the checksum it leaves on this content."""
        self.connection.on_commit(
            partial(self.tasks.__setitem__, content_id, signature)
        )

    @contextmanager
    def track_write(self, content):
        using = self.connection.alias
        contents = WebsiteContent.all_objects.using(using)
        with transaction.atomic(using=using):
            # Bulk edits can leave the sync state's checksum behind the content.
            previous = (
                contents.select_for_update(of=("self",))
                .annotate(synced_checksum=F("content_sync_state__synced_checksum"))
                .filter(pk=content.pk)
                .first()
                if content.pk is not None
                else None
            )
            before = previous.calculate_checksum() if previous is not None else None
            synced = previous.synced_checksum if previous is not None else None
            yield
            saved = contents.get(pk=content.pk)
            current = saved.calculate_checksum()
            if before != current:
                self.connection.on_commit(
                    partial(self.record_change, content.pk, before, synced, current)
                )
            old_path = str(previous.file).lstrip("/") if previous is not None else ""
            new_path = str(saved.file).lstrip("/")
            if old_path != new_path:
                self.connection.on_commit(
                    partial(self.record_file_change, content.pk, old_path, new_path)
                )

    def _changed_ids(self, worker_checksums):
        reverted = {
            pk
            for pk, change in self.changes.items()
            if worker_checksums.get(pk, change.current) == change.original
        }
        required = (self.changes.keys() | worker_checksums.keys()) - reverted
        # A concurrent sync may have published an intermediate version between writes.
        synced_versions = ContentSyncState.objects.using(self.connection.alias).filter(
            content_id__in=reverted, synced_checksum__isnull=False
        )
        for pk, synced in synced_versions.values_list("content_id", "synced_checksum"):
            change = self.changes[pk]
            if synced not in (change.originally_synced, change.original):
                required.add(pk)
        return required

    def _required_url_targets(self, changed):
        target_ids = {pk for source, pk in self.url_references if source in changed}
        targets = (
            WebsiteContent.objects.using(self.connection.alias)
            .filter(pk__in=target_ids)
            .select_related("content_sync_state", "website__starter")
        )
        backends = {}
        for target in targets.iterator():
            state = getattr(target, "content_sync_state", None)
            if state is None or state.synced_checksum is None:
                yield target.pk
                continue
            if not target.website.starter_id:
                continue
            path = get_destination_filepath(
                target, SiteConfig(target.website.starter.config)
            )
            if not path:
                continue
            if old_path := (state.data or {}).get(GIT_DATA_FILEPATH):
                if path != old_path:
                    yield target.pk
                continue
            # Git imports can record the checksum without the filepath.
            if target.website_id not in backends:
                backends[target.website_id] = api.get_sync_backend(target.website)
            if not backends[target.website_id].file_exists(path):
                yield target.pk

    def prepare_sync(self, worker_checksums=None):
        """Include dependent Git files and mark stale paths for serialization."""
        using = self.connection.alias
        changed = self._changed_ids(worker_checksums or {})
        required = set(changed)
        targets_by_site = defaultdict(set)
        for source_id, website_id, text_id in self.references:
            if source_id in changed:
                targets_by_site[website_id].add(text_id)
        for website_id, text_ids in targets_by_site.items():
            targets = WebsiteContent.objects.using(using).filter(
                website_id=website_id,
                text_id__in=text_ids,
                content_sync_state__synced_checksum__isnull=True,
            )
            required.update(targets.values_list("pk", flat=True))

        files = (
            WebsiteContent.objects.using(using)
            .filter(pk__in=self.changed_files)
            .values_list("website_id", "text_id", named=True)
        )
        dependencies = videos_referencing_renamed_files(files, using=using)
        dependencies.update(self._required_url_targets(changed))
        # Keep the last Git filepath so a moved target can remove its old file.
        ContentSyncState.objects.using(using).filter(
            content_id__in=dependencies, synced_checksum__isnull=False
        ).update(synced_checksum=None)
        return sorted(required | dependencies)


@contextmanager
def collect_repaired_content():
    """Collect committed changes on the command's database connection."""
    scope = _RepairScope(transaction.get_connection())
    token = _active_repair.set(scope)
    try:
        yield scope
    finally:
        _active_repair.reset(token)


def active_repair(using):
    """Return the repair collecting writes on this connection."""
    scope = _active_repair.get()
    if scope is not None and transaction.get_connection(using) is scope.connection:
        return scope
    return None


def track_repair_write(content, using):
    """Wrap one content row write while a repair is collecting changes."""
    scope = active_repair(using)
    return scope.track_write(content) if scope is not None else nullcontext()
