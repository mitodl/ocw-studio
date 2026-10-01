"""Remove legacy UUID prefixes from resource filenames in S3."""  # noqa: INP001

import csv
import sys
from collections import defaultdict
from pathlib import PurePosixPath
from typing import NamedTuple

from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q, TextField
from django.db.models.functions import Cast
from mitol.common.utils import now_in_utc

from content_sync.models import ContentSyncState
from content_sync.tasks import sync_website_content
from gdrive_sync.models import DriveFile
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_client
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.filename_references import (
    build_path_lookup,
    rewrite_file_references,
    rewrite_json_strings,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.rules.gallery_image_rename import (
    GALLERY_ITEM_SHORTCODE_NAME,
    BaseGalleryHrefRewriteRule,
)
from websites.models import Website, WebsiteContent
from websites.utils import (
    UUID_FILENAME_RE,
    get_dict_field,
    get_dict_query_field,
    strip_uuid_prefix,
)


class RenameTask(NamedTuple):
    """A planned S3 + DB rename for one WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    website_id: str  # str(Website.uuid) — UUID FK used for dirty-flag bulk update
    text_id: str  # WebsiteContent.text_id — what a gallery item's uuid param names
    old_key: str
    new_key: str
    suffixed: bool = False  # new_key is not simply old_key with the prefix removed
    reason: str = ""  # contested, name held by existing file, shared object


class MetadataPatch(NamedTuple):
    """A planned metadata update for one Video-type WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    updated_metadata: dict


class MarkdownPatch(NamedTuple):
    """A planned markdown update for one WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    updated_markdown: str
    gallery: bool = False  # an image-gallery-item href changed
    links: bool = False  # a path reference to a renamed file changed


class SiteMetadataPatch(NamedTuple):
    """A planned metadata update for one Website record."""

    website_id: str  # str(Website.uuid)
    updated_metadata: dict


def _with_suffix(key: str, number: int) -> str:
    """Insert -<number> before the last extension of *key*'s file name."""
    directory, separator, name = key.rpartition("/")
    path = PurePosixPath(name)
    return f"{directory}{separator}{path.stem}-{number}{path.suffix}"


class _PlannedGalleryHrefRule(BaseGalleryHrefRewriteRule):
    """
    Resolve image-gallery-item hrefs using this run's exact rename plan.

    Unlike GalleryImageRenameRule (which infers renames from current
    WebsiteContent state for standalone backfills), this uses the precise
    mapping already computed by _collect_renames, scoped per website. This
    means it works correctly even before any rename has been applied to the
    database, so the same logic can back both the --dry-run preview and the
    live-run patch.

    An item's uuid param names the resource being renamed, so it is matched
    first and does not care whether the href was accurate to begin with.
    Items the uuid backfill left alone fall back to the old basename. Either
    way only files in this run's plan are in the maps, so a collision skip
    can never be matched.
    """

    alias = "planned_gallery_href_rewrite"  # internal use only; not CLI-registered

    def __init__(
        self,
        basename_map: dict[str, dict[str, str]],
        uuid_map: dict[str, dict[str, str]],
    ):
        super().__init__()
        self.basename_map = basename_map
        self.uuid_map = uuid_map

    def resolve_new_href(self, website_id, href, uuid):
        site = str(website_id)
        # A rename only ever changes the basename, so match on the basename
        # and put the href's own prefix back.
        prefix, sep, basename = href.rpartition("/")
        new_basename = None
        if uuid:
            new_basename = self.uuid_map.get(site, {}).get(uuid)
        if new_basename is None:
            new_basename = self.basename_map.get(site, {}).get(basename)
        if new_basename is None or new_basename == basename:
            return None
        return f"{prefix}{sep}{new_basename}"


_REASON_CONTESTED = "contested"
_REASON_HELD = "name held by existing file"
_REASON_SHARED = "shared object"


def _collect_renames(queryset):
    """
    Plan the rename of every UUID-prefixed file in *queryset*.

    Returns (tasks, skipped_count). A file whose stripped name would clash
    gets a numbered suffix rather than being skipped, see _assign_targets.
    Two things are still skipped: a name that would be empty after
    stripping, and an S3 object also used by a row in a website outside this
    run, since renaming it for one row would delete the object the other
    still uses.
    """
    skipped = 0
    sources = defaultdict(list)  # normalised old key -> rows using it
    for content in queryset.iterator():
        old_key = str(content.file)
        if strip_uuid_prefix(old_key) != old_key:
            sources[old_key.lstrip("/")].append(content)
            continue
        basename = old_key.rpartition("/")[2]
        if UUID_FILENAME_RE.match(basename) and not basename[33:]:
            print(  # noqa: T201
                f"Skipping {old_key}: filename would be empty after removing UUID prefix",  # noqa: E501
                file=sys.stderr,
            )
            skipped += 1

    skipped += _drop_sources_shared_outside(sources, queryset)
    targets = _assign_targets(sources, _taken_keys())

    tasks = []
    for source_key in sorted(sources, key=lambda key: _first_pk(sources[key])):
        target, reason = targets[source_key]
        plain = strip_uuid_prefix(source_key)
        for content in sorted(sources[source_key], key=lambda row: row.pk):
            old_key = str(content.file)
            lead = "/" if old_key.startswith("/") else ""
            tasks.append(
                RenameTask(
                    pk=str(content.pk),
                    website_id=str(content.website_id),
                    text_id=str(content.text_id),
                    old_key=old_key,
                    new_key=f"{lead}{target}",
                    suffixed=target != plain,
                    reason=reason,
                )
            )
    return tasks, skipped


def _first_pk(rows):
    """Return the lowest pk among rows sharing a source, which orders contests."""
    return min(row.pk for row in rows)


def _taken_keys():
    """
    Every key some row holds today, normalised without a leading slash.

    Built from all_objects across every website, so a filtered run cannot
    hand out a name another site already holds, and a soft-deleted row's
    key, whose S3 object may still exist, is never reused.
    """
    return {
        file_value.lstrip("/")
        for file_value in WebsiteContent.all_objects.exclude(file="")
        .exclude(file__isnull=True)
        .values_list("file", flat=True)
        .iterator(chunk_size=5000)
        if file_value
    }


def _drop_sources_shared_outside(sources, queryset):
    """
    Remove sources that a live row outside *queryset*'s websites also uses.

    Returns how many rows were dropped.
    """
    selected = {
        str(website_id)
        for website_id in queryset.values_list("website_id", flat=True).distinct()
    }
    outside = defaultdict(set)
    for file_value, website_id in (
        WebsiteContent.objects.exclude(file="")
        .exclude(file__isnull=True)
        .values_list("file", "website_id")
        .iterator(chunk_size=5000)
    ):
        key = file_value.lstrip("/")
        if key in sources and str(website_id) not in selected:
            outside[key].add(website_id)
    dropped = 0
    for source_key, website_ids in outside.items():
        names = ", ".join(
            sorted(
                Website.objects.filter(uuid__in=website_ids).values_list(
                    "name", flat=True
                )
            )
        )
        print(  # noqa: T201
            f"Skipping {source_key}: the same S3 object is used by {names}, "
            "which this run does not include. Run those websites together.",
            file=sys.stderr,
        )
        dropped += len(sources.pop(source_key))
    return dropped


def _assign_targets(sources, taken):
    """
    Choose the final key for every source object.

    Returns {source_key: (target_key, reason)}, keys normalised without a
    leading slash. A target is contested when two or more sources want it,
    or when some row already holds it. Names are compared ignoring case,
    because offline downloads unzip onto case-insensitive disks, where
    Lecture1.pdf and lecture1.pdf are one file. Every plain name that can be
    given out is claimed before any suffix, so a suffix never takes a name
    another file would get as is. Within a group, sources go in order of
    their lowest pk: the first keeps its plain name unless it is held, and
    the rest count up from -2 on their own name, skipping anything taken or
    already claimed.
    """
    taken = {key.lower() for key in taken}
    wanted_by = defaultdict(list)
    for source_key in sources:
        wanted_by[strip_uuid_prefix(source_key).lower()].append(source_key)
    for group in wanted_by.values():
        group.sort(key=lambda key: _first_pk(sources[key]))

    assigned = {}
    claimed = set()
    for folded, group in sorted(wanted_by.items()):
        if folded not in taken:
            assigned[group[0]] = strip_uuid_prefix(group[0])
            claimed.add(folded)
    for group in (group for _, group in sorted(wanted_by.items())):
        number = 2
        for source_key in group:
            if source_key in assigned:
                continue
            plain = strip_uuid_prefix(source_key)
            candidate = _with_suffix(plain, number)
            while candidate.lower() in taken or candidate.lower() in claimed:
                number += 1
                candidate = _with_suffix(plain, number)
            assigned[source_key] = candidate
            claimed.add(candidate.lower())
            number += 1

    return {
        source_key: (
            assigned[source_key],
            _reason(sources[source_key], group, folded in taken),
        )
        for folded, group in wanted_by.items()
        for source_key in group
    }


def _reason(rows, group, held):
    """Explain a rename for the CSV: why it is not a plain, solo rename."""
    reasons = []
    if len(group) > 1:
        reasons.append(_REASON_CONTESTED)
    if held:
        reasons.append(_REASON_HELD)
    if len(rows) > 1:
        reasons.append(_REASON_SHARED)
    return ", ".join(reasons)


def _collect_markdown_patches(renames, lookup):
    """
    Patch gallery hrefs and file links in markdown, one final value per row.

    Gallery pages in the renamed websites get the plan-driven href rewrite
    first, then every page naming a legacy file gets the path rewrite on
    that output. Doing both in one pass matters: two bulk_updates of the
    same column would let the second drop the first. A path-valued gallery
    href is rewritten once, since the path pass no longer sees a prefix.

    Returns list[MarkdownPatch] and writes nothing, so it backs both the dry
    run and the live run. A page that cannot be processed is skipped with a
    warning rather than aborting the scan: legacy markdown across tens of
    thousands of pages cannot be assumed to parse, and one bad page must not
    cost every other page its fix.
    """
    if not renames:
        return []

    basename_map: dict[str, dict[str, str]] = {}
    uuid_map: dict[str, dict[str, str]] = {}
    for task in renames:
        old_basename = task.old_key.rpartition("/")[2]
        new_basename = task.new_key.rpartition("/")[2]
        basename_map.setdefault(task.website_id, {})[old_basename] = new_basename
        uuid_map.setdefault(task.website_id, {})[task.text_id] = new_basename

    cleaner = WebsiteContentMarkdownCleaner(
        _PlannedGalleryHrefRule(basename_map, uuid_map)
    )
    contents = (
        WebsiteContent.objects.filter(
            Q(
                website__uuid__in=basename_map.keys(),
                markdown__contains=GALLERY_ITEM_SHORTCODE_NAME,
            )
            | Q(markdown__iregex=_LEGACY_NAME_PATTERN)
        )
        .exclude(markdown="")
        .exclude(markdown__isnull=True)
        .iterator()
    )
    patches = []
    for wc in contents:
        try:
            gallery = str(wc.website_id) in basename_map and (
                cleaner.update_website_content(wc)
            )
            linked = rewrite_file_references(wc.markdown, lookup)
        except Exception as exc:  # noqa: BLE001
            print(  # noqa: T201
                f"Skipping markdown patch for content pk={wc.pk}: {exc!s}",
                file=sys.stderr,
            )
            continue
        finally:
            # Discard per-match bookkeeping the cleaner isn't asked to report
            # here, or it grows across a large scan and keeps every scanned
            # page alive. A page that raised part way through has already
            # recorded its earlier matches, so this runs on that path too.
            cleaner.replacement_matches.clear()
        links = linked != wc.markdown
        if gallery or links:
            patches.append(
                MarkdownPatch(
                    pk=str(wc.pk),
                    updated_markdown=linked,
                    gallery=bool(gallery),
                    links=links,
                )
            )
    return patches


# Matches a legacy UUID file name anywhere in a text column, for pre-filtering.
_LEGACY_NAME_PATTERN = r"[0-9a-f]{32}_"


class Followups(NamedTuple):
    """Every reference patch computed for one set of renames."""

    metadata: list  # MetadataPatch
    markdown: list  # MarkdownPatch
    site_metadata: list  # SiteMetadataPatch
    videos: set  # pks of videos to write to git again


def _site_paths(website_ids):
    """Map website id to (s3_path, url_path), for resolving path references."""
    return {
        str(website.uuid): (
            website.s3_path if website.starter_id else None,
            website.url_path,
        )
        for website in Website.objects.filter(uuid__in=website_ids).select_related(
            "starter"
        )
    }


def _collect_content_metadata_patches(lookup):
    """
    Rewrite path references to renamed files in every content metadata value.

    Every website is scanned, not only the renamed ones, because a page can
    point at another site's file. This replaces a video-only patch that
    worked out new names by stripping the prefix, which cannot follow a file
    that got a suffix.
    """
    if not lookup:
        return []
    patches = []
    rows = (
        WebsiteContent.objects.annotate(metadata_text=Cast("metadata", TextField()))
        .filter(metadata_text__iregex=_LEGACY_NAME_PATTERN)
        .values_list("pk", "metadata")
        .iterator(chunk_size=2000)
    )
    for pk, metadata in rows:
        try:
            updated, changed = rewrite_json_strings(metadata, lookup)
        except Exception as exc:  # noqa: BLE001
            print(  # noqa: T201
                f"Skipping metadata patch for content pk={pk}: {exc!s}",
                file=sys.stderr,
            )
            continue
        if changed:
            patches.append(MetadataPatch(pk=str(pk), updated_metadata=updated))
    return patches


def _collect_site_metadata_patches(lookup):
    """
    Rewrite path references to renamed files in every website's metadata.

    Covers the legacy course_image_url and course_thumbnail_image_url
    values, and any other string there that names a renamed file.
    """
    if not lookup:
        return []
    patches = []
    rows = (
        Website.objects.annotate(metadata_text=Cast("metadata", TextField()))
        .filter(metadata_text__iregex=_LEGACY_NAME_PATTERN)
        .values_list("uuid", "metadata")
        .iterator(chunk_size=2000)
    )
    for uuid, metadata in rows:
        try:
            updated, changed = rewrite_json_strings(metadata, lookup)
        except Exception as exc:  # noqa: BLE001
            print(  # noqa: T201
                f"Skipping metadata patch for website {uuid}: {exc!s}",
                file=sys.stderr,
            )
            continue
        if changed:
            patches.append(
                SiteMetadataPatch(website_id=str(uuid), updated_metadata=updated)
            )
    return patches


def _linked_videos(renames):
    """
    Return the pks of videos whose captions or transcripts are in *renames*.

    A video links these by the resource's text_id, and full_metadata()
    resolves that to a file path only when the video is written to git.
    Renaming the file changes the resource's checksum but not the video's,
    so without a fresh sync the video's git copy keeps the old path, and the
    next publish removes the file it points at.
    """
    text_ids = defaultdict(set)
    for task in renames:
        text_ids[task.website_id].add(task.text_id)
    if not text_ids:
        return set()
    resource_type = get_dict_query_field("metadata", settings.FIELD_RESOURCETYPE)
    videos = WebsiteContent.objects.filter(
        website__uuid__in=text_ids.keys(), **{resource_type: RESOURCE_TYPE_VIDEO}
    ).values_list("pk", "website_id", "metadata")
    pks = set()
    for pk, website_id, metadata in videos.iterator(chunk_size=2000):
        for field in (
            settings.YT_FIELD_CAPTIONS_RESOURCES,
            settings.YT_FIELD_TRANSCRIPT_RESOURCES,
        ):
            linked = get_dict_field(metadata or {}, f"{field}.content") or []
            if isinstance(linked, str):
                linked = [linked]
            if text_ids[str(website_id)].intersection(map(str, linked)):
                pks.add(pk)
                break
    return pks


def _collect_followups(renames):
    """
    Compute every reference patch for *renames* without writing anything.

    Backs both the dry run, from the whole plan, and the live run, from the
    renames that committed.
    """
    if not renames:
        return Followups(metadata=[], markdown=[], site_metadata=[], videos=set())
    lookup = build_path_lookup(
        renames, _site_paths({task.website_id for task in renames})
    )
    return Followups(
        metadata=_collect_content_metadata_patches(lookup),
        markdown=_collect_markdown_patches(renames, lookup),
        site_metadata=_collect_site_metadata_patches(lookup),
        videos=_linked_videos(renames),
    )


def _apply_followups(committed):
    """
    Write every reference patch for the renames that committed.

    Scoped to committed renames only, so a skipped or failed file leaves the
    references to it alone.
    """
    website_ids = {task.website_id for task in committed}
    if website_ids:
        Website.objects.filter(uuid__in=website_ids).update(
            has_unpublished_live=True,
            has_unpublished_draft=True,
        )
    followups = _collect_followups(committed)
    WebsiteContent.objects.bulk_update(
        [
            WebsiteContent(pk=patch.pk, metadata=patch.updated_metadata)
            for patch in followups.metadata
        ],
        ["metadata"],
        batch_size=_SYNC_STATE_BATCH,
    )
    WebsiteContent.objects.bulk_update(
        [
            WebsiteContent(pk=patch.pk, markdown=patch.updated_markdown)
            for patch in followups.markdown
        ],
        ["markdown"],
        batch_size=_SYNC_STATE_BATCH,
    )
    Website.objects.bulk_update(
        [
            Website(uuid=patch.website_id, metadata=patch.updated_metadata)
            for patch in followups.site_metadata
        ],
        ["metadata"],
        batch_size=_SYNC_STATE_BATCH,
    )
    # These writes bypass post_save, so the sync states still carry the old
    # checksums. Refresh them, or the git sync treats this content as
    # already synced and the published site keeps the old file names.
    _refresh_sync_states(
        {patch.pk for patch in followups.metadata}
        | {patch.pk for patch in followups.markdown}
    )
    # A video's own checksum does not change, so clear its synced checksum.
    ContentSyncState.objects.filter(content_id__in=followups.videos).update(
        synced_checksum=None
    )
    return followups


_SYNC_STATE_BATCH = 2000
# A site's git commit is slow but not unbounded. Without a cap the command
# blocks forever if no worker ever picks the task up.
_SYNC_TIMEOUT_SECONDS = 600


def _refresh_sync_states(pks):
    """
    Recompute ContentSyncState.current_checksum for *pks*.

    Every write in this command goes through update()/bulk_update() for speed,
    which skips WebsiteContent.save() and so never fires the post_save receiver
    that normally keeps this column current. Left alone the row keeps
    current_checksum == synced_checksum, which upsert_content_files_for_user
    reads as "already synced" and excludes before its in-loop recompute can
    correct it, so the change never reaches git and the published site keeps
    serving the old content.
    """
    pks = list(pks)
    if not pks:
        return
    # Chunked because a full run hands this tens of thousands of pks. Postgres
    # does not cap bulk_batch_size, so an unbatched bulk_update would build one
    # UPDATE with a CASE branch per record, and the IN clause would pull every
    # sync state into memory at once.
    for start in range(0, len(pks), _SYNC_STATE_BATCH):
        chunk = pks[start : start + _SYNC_STATE_BATCH]
        states = {
            state.content_id: state
            for state in ContentSyncState.objects.filter(content_id__in=chunk)
        }
        stale = []
        for content in WebsiteContent.objects.filter(pk__in=chunk).iterator():
            state = states.get(content.pk)
            if state is None:
                continue
            checksum = content.calculate_checksum()
            if state.current_checksum != checksum:
                state.current_checksum = checksum
                stale.append(state)
        if stale:
            ContentSyncState.objects.bulk_update(
                stale, ["current_checksum"], batch_size=_SYNC_STATE_BATCH
            )


class ExecutionResult(NamedTuple):
    """What a rename pass actually did."""

    committed: list  # RenameTask rows whose rename committed
    error_count: int


# How many source objects share one database recheck of their targets.
_RECHECK_BATCH = 500


def _current_holders(keys):
    """Map each normalised key in *keys* to the pks of every row holding it now."""
    variants = set(keys) | {f"/{key}" for key in keys}
    holders = defaultdict(set)
    for file_value, pk in WebsiteContent.all_objects.filter(
        file__in=variants
    ).values_list("file", "pk"):
        holders[file_value.lstrip("/")].add(pk)
    return holders


def _execute_renames(renames, s3, stdout, stderr):
    """
    Apply the plan: one S3 copy per source object, one transaction per row.

    Rows are grouped by source key, so a shared object is copied once and
    its old key is deleted only after every row pointing at it committed.
    Each batch of targets is checked against the database again first. A
    full run takes hours, and Google Drive sync creates keys without a UUID
    prefix, so a colliding key can appear after planning.
    """
    groups = defaultdict(list)
    for task in renames:
        groups[task.old_key.lstrip("/")].append(task)
    source_keys = list(groups)
    committed = []
    error_count = 0
    for start in range(0, len(source_keys), _RECHECK_BATCH):
        batch = source_keys[start : start + _RECHECK_BATCH]
        holders = _current_holders(
            {groups[key][0].new_key.lstrip("/") for key in batch}
        )
        for source_key in batch:
            done, errors = _rename_group(
                source_key, groups[source_key], holders, s3, stdout, stderr
            )
            committed.extend(done)
            error_count += errors
    return ExecutionResult(committed=committed, error_count=error_count)


def _rename_group(source_key, tasks, holders, s3, stdout, stderr):  # noqa: PLR0913, PLR0917
    """
    Rename one source object and every row that points at it.

    Returns (committed tasks, error count). The old key is deleted only when
    every row committed, since a row that failed still points at it.
    """
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    target = tasks[0].new_key.lstrip("/")
    if holders.get(target, set()) - {int(task.pk) for task in tasks}:
        stderr.write(
            f"Error renaming {source_key}: target {target} was taken after "
            "planning. Run the command again to give it a new name."
        )
        return [], len(tasks)
    try:
        s3.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": source_key},
            Key=target,
            ACL="public-read",
        )
    except Exception as exc:  # noqa: BLE001
        for task in tasks:
            stderr.write(f"Error renaming {task.old_key} to {task.new_key}: {exc!s}")
        return [], len(tasks)
    committed = []
    for task in tasks:
        if _commit_row(task, source_key, target, stderr):
            stdout.write(f"Renamed: {task.old_key} -> {task.new_key}")
            committed.append(task)
    if len(committed) < len(tasks):
        stderr.write(f"Keeping {source_key}: a row still points at it")
        return committed, len(tasks) - len(committed)
    try:
        s3.delete_object(Bucket=bucket, Key=source_key)
    except Exception as exc:  # noqa: BLE001
        # The rename is committed in the database and S3, so the old key is
        # only an orphan now. Warn and keep the success.
        stderr.write(f"Warning: failed to delete old key {source_key}: {exc!s}")
    return committed, 0


def _commit_row(task, source_key, target, stderr):
    """Commit one row's rename in its own transaction. Return True on success."""
    try:
        with transaction.atomic():
            WebsiteContent.objects.filter(pk=task.pk).update(file=task.new_key)
            DriveFile.objects.filter(resource_id=task.pk, s3_key=source_key).update(
                s3_key=target
            )
            # Inside the same transaction as the rename it belongs to.
            # Deferring it would leave an interrupted run's committed renames
            # with a stale checksum, and a re-run cannot find them, since they
            # no longer carry a prefix.
            _refresh_sync_states([task.pk])
    except Exception as exc:  # noqa: BLE001
        stderr.write(f"Error renaming {task.old_key} to {task.new_key}: {exc!s}")
        return False
    return True


_CSV_FIELDNAMES = [
    "pk",
    "website_id",
    "website_name",
    "old_key",
    "new_key",
    "suffixed",
    "reason",
]


def _write_csv_rows(writer, renames, website_names):
    """Write header + one row per RenameTask to *writer*."""
    writer.writeheader()
    for task in renames:
        writer.writerow(
            {
                "pk": task.pk,
                "website_id": task.website_id,
                "website_name": website_names.get(task.website_id, ""),
                "old_key": task.old_key,
                "new_key": task.new_key,
                "suffixed": "yes" if task.suffixed else "no",
                "reason": task.reason,
            }
        )


def _summary(renames, skipped, followups, *, dry_run, errors=0):
    """Build one line of counts, worded for a dry run or a live run."""
    suffixed = sum(1 for task in renames if task.suffixed)
    shared = len(
        {task.old_key.lstrip("/") for task in renames if _REASON_SHARED in task.reason}
    )
    would = "would be " if dry_run else ""
    parts = [
        f"{len(renames) - suffixed} files {would}renamed",
        f"{suffixed} files {would}renamed with a suffix",
        f"{shared} shared S3 objects",
        f"{skipped} skipped",
    ]
    if not dry_run:
        parts.append(f"{errors} errors")
    links = sum(1 for patch in followups.markdown if patch.links)
    galleries = sum(1 for patch in followups.markdown if patch.gallery)
    parts += [
        f"{len(followups.metadata)} content metadata records {would}patched",
        f"{links} pages with file links {would}patched",
        f"{len(followups.site_metadata)} site metadata records {would}patched",
        f"{galleries} gallery pages {would}patched",
        f"{len(followups.videos)} video pages {would}synced again",
    ]
    return ", ".join(parts)


class Command(WebsiteFilterCommand):
    """Remove legacy UUID prefixes from resource filenames in S3 and update database records."""  # noqa: E501

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Export a rename plan CSV without making any changes",
        )
        parser.add_argument(
            "--output",
            dest="output",
            default=None,
            help="File path for the CSV plan. Required with --dry-run.",
        )
        parser.add_argument(
            "-ss",
            "--skip-sync",
            dest="skip_sync",
            action="store_true",
            default=False,
            help="Whether to skip syncing the changed websites to the backend",
        )

    def _sync_backend(self, *, skip_sync, website_ids):
        """
        Push the changed websites to the configured content-sync backend.

        Scoped to the sites this run actually touched. The alternative,
        sync_unsynced_websites, takes no filter and walks every site with
        unsynced content, so a --filter run would push unrelated sites that
        happened to be pending.
        """
        if not settings.CONTENT_SYNC_BACKEND or skip_sync or not website_ids:
            return
        names = list(
            Website.objects.filter(uuid__in=website_ids).values_list("name", flat=True)
        )
        if not names:
            return
        self.stdout.write(f"Syncing {len(names)} website(s) to the backend")
        start = now_in_utc()
        failed = []
        # One site at a time. sync_website_content has no rate-limit throttle of
        # its own (unlike sync_unsynced_websites), so dispatching every site at
        # once would put the whole batch against the git backend's API limit
        # simultaneously. A site that fails is reported rather than aborting the
        # command, since by this point every rename has already committed.
        for index, name in enumerate(names):
            try:
                sync_website_content.delay(name).get(timeout=_SYNC_TIMEOUT_SECONDS)
            except CeleryTimeoutError:
                # get(timeout) bounds our wait, it does not stop the worker, so
                # that task is still running. Dispatching the next site now
                # would let syncs overlap, which is what serialising this loop
                # was meant to avoid. A timeout points at an unhealthy worker
                # pool or backend, so stop rather than piling on more work.
                failed.extend(names[index:])
                self.stderr.write(
                    f"Timed out after {_SYNC_TIMEOUT_SECONDS}s waiting for {name}, "
                    "stopping before the remaining site(s)"
                )
                break
            except Exception as exc:  # noqa: BLE001
                # The task finished and failed, so nothing is still holding the
                # backend. Safe to carry on to the next site.
                failed.append(name)
                self.stderr.write(f"Failed to sync {name}: {exc!s}")
        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            f"Backend sync finished for {len(names) - len(failed)} of {len(names)} "
            f"website(s) in {total_seconds} seconds"
        )
        if failed:
            self.stderr.write(
                f"{len(failed)} website(s) did not sync and still need publishing: "
                f"{', '.join(sorted(failed))}"
            )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        dry_run = options["dry_run"]

        contents = self.filter_website_contents(
            WebsiteContent.objects.filter(file__isnull=False).exclude(file="")
        )

        # --- Discovery phase (no S3/DB writes) ---
        renames, skipped_count = _collect_renames(contents)

        if dry_run:
            output_path = options.get("output")
            if not output_path:
                msg = "--output is required when using --dry-run"
                raise CommandError(msg)
            planned_website_ids = {task.website_id for task in renames}
            # Look up website names for the human-readable CSV column.
            # Use str(uuid) as key to match task.website_id (already stringified).
            website_names = (
                {
                    str(uuid): name
                    for uuid, name in Website.objects.filter(
                        uuid__in=planned_website_ids
                    ).values_list("uuid", "name")
                }
                if planned_website_ids
                else {}
            )
            # Write the CSV rename plan before scanning for references: the
            # plan is the operator's safety artifact and must not depend on
            # markdown parsing succeeding. The patchers guard per record
            # internally, but this ordering means even an unanticipated
            # failure there can't cost the CSV export.
            with open(output_path, "w", newline="", encoding="utf-8") as f:  # noqa: PTH123
                _write_csv_rows(
                    csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES),
                    renames,
                    website_names,
                )
            followups = _collect_followups(renames)
            self.stdout.write(
                "Dry run complete: "
                f"{_summary(renames, skipped_count, followups, dry_run=True)}. "
                f"Plan written to {output_path}."
            )
            return

        # --- Execution phase ---
        s3 = get_boto3_client("s3")
        result = _execute_renames(renames, s3, self.stdout, self.stderr)

        followups = _apply_followups(result.committed)

        summary = _summary(
            result.committed,
            skipped_count,
            followups,
            dry_run=False,
            errors=result.error_count,
        )
        self.stdout.write(f"Done: {summary}")

        self._sync_backend(
            skip_sync=options["skip_sync"],
            website_ids={task.website_id for task in result.committed},
        )
