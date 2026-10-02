"""Remove legacy UUID prefixes from resource filenames in S3."""  # noqa: INP001

import csv
import logging
import sys
import time
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import NamedTuple

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q, TextField
from django.db.models.functions import Cast

from content_sync.models import ContentSyncState
from gdrive_sync.models import DriveFile
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_client
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.filename_references import (
    build_path_index,
    build_path_lookup,
    referenced_entries,
    referenced_entries_in_json,
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

log = logging.getLogger(__name__)


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
    that output, as the job does per row. A path-valued gallery href is
    rewritten once, since the path pass no longer sees a prefix.

    Returns list[MarkdownPatch] and writes nothing, for the dry run's
    report. A page that cannot be processed is skipped with a
    warning rather than aborting the scan: legacy markdown across tens of
    thousands of pages cannot be assumed to parse, and one bad page must not
    cost every other page its fix.
    """
    if not renames:
        return []

    basename_map, uuid_map = _gallery_maps(renames)
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


def _with_own_file(metadata, old_key, new_key):
    """
    Point a renamed row's own metadata["file"] at its new key.

    The value mirrors the row's file, but some mirrors cannot be parsed as a
    path reference: names with a space or parentheses, or a path missing the
    site directory. It is matched by file name and keeps its leading slash.
    """
    value = metadata.get("file") if isinstance(metadata, dict) else None
    if not isinstance(value, str):
        return metadata, False
    if value.rpartition("/")[2] != old_key.rpartition("/")[2]:
        return metadata, False
    lead = "/" if value.startswith("/") else ""
    return {**metadata, "file": f"{lead}{new_key.lstrip('/')}"}, True


def _collect_content_metadata_patches(lookup, own_files):
    """
    Rewrite path references to renamed files in every content metadata value.

    Every website is scanned, not only the renamed ones, because a page can
    point at another site's file. This replaces a video-only patch that
    worked out new names by stripping the prefix, which cannot follow a file
    that got a suffix. *own_files* maps a renamed row's pk to its (old key,
    new key), for its own metadata["file"].
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
            if pk in own_files:
                updated, own_changed = _with_own_file(updated, *own_files[pk])
                changed = changed or own_changed
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


def _gallery_maps(renames):
    """Build the per-website maps that _PlannedGalleryHrefRule reads."""
    basename_map: dict[str, dict[str, str]] = {}
    uuid_map: dict[str, dict[str, str]] = {}
    for task in renames:
        old_basename = task.old_key.rpartition("/")[2]
        new_basename = task.new_key.rpartition("/")[2]
        basename_map.setdefault(task.website_id, {})[old_basename] = new_basename
        uuid_map.setdefault(task.website_id, {})[task.text_id] = new_basename
    return basename_map, uuid_map


class PatchCounts(NamedTuple):
    """How many rows one patch pass changed, by location."""

    content_metadata: int
    markdown_links: int
    galleries: int
    site_metadata: int
    errors: int


def _patch_rows(committed, content_pks, website_ids):
    """
    Apply the follow-up patches for *committed*, one locked row at a time.

    Chunks run concurrently, and two can reach the same row, e.g. a page
    linking to another site's file, or a gallery page whose images sit in
    two chunks. Each row is locked with select_for_update, re-read and
    rewritten from its current value, so a second chunk builds on the first
    chunk's change instead of overwriting it. *content_pks* and
    *website_ids* are the rows the job's plan found referencing these files.
    Gallery pages are found here by website, because an item can name its
    image through the uuid param alone.
    """
    if not committed:
        return PatchCounts(0, 0, 0, 0, 0)
    renamed_sites = {task.website_id for task in committed}
    lookup = build_path_lookup(committed, _site_paths(renamed_sites))
    cleaner = WebsiteContentMarkdownCleaner(
        _PlannedGalleryHrefRule(*_gallery_maps(committed))
    )
    gallery_pks = WebsiteContent.objects.filter(
        website__uuid__in=renamed_sites,
        markdown__contains=GALLERY_ITEM_SHORTCODE_NAME,
    ).values_list("pk", flat=True)
    counts = Counter()
    own_files = {int(task.pk): (task.old_key, task.new_key) for task in committed}
    for pk in sorted(set(content_pks) | set(gallery_pks) | set(own_files)):
        try:
            counts.update(
                _patch_content_row(
                    pk, lookup, cleaner, renamed_sites, own_files.get(pk)
                )
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping reference patch for content pk=%s: %s", pk, exc)
            counts["errors"] += 1
        finally:
            cleaner.replacement_matches.clear()
    for website_id in sorted(set(website_ids)):
        try:
            counts["site_metadata"] += int(_patch_site_row(website_id, lookup))
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping reference patch for website %s: %s", website_id, exc)
            counts["errors"] += 1
    return PatchCounts(
        content_metadata=counts["content_metadata"],
        markdown_links=counts["markdown_links"],
        galleries=counts["galleries"],
        site_metadata=counts["site_metadata"],
        errors=counts["errors"],
    )


def _patch_content_row(pk, lookup, cleaner, renamed_sites, own_file):
    """
    Lock, re-read and patch one content row. Return which parts changed.

    *own_file* is the row's own (old key, new key) when it was renamed.
    """
    with transaction.atomic():
        wc = WebsiteContent.objects.select_for_update().filter(pk=pk).first()
        if wc is None:
            return {}
        gallery = bool(
            str(wc.website_id) in renamed_sites
            and wc.markdown
            and cleaner.update_website_content(wc)
        )
        markdown = rewrite_file_references(wc.markdown, lookup)
        links = markdown != wc.markdown
        metadata, metadata_changed = rewrite_json_strings(wc.metadata, lookup)
        if own_file:
            metadata, own_changed = _with_own_file(metadata, *own_file)
            metadata_changed = metadata_changed or own_changed
        updates = {}
        if gallery or links:
            updates["markdown"] = markdown
        if metadata_changed:
            updates["metadata"] = metadata
        if not updates:
            return {}
        WebsiteContent.objects.filter(pk=pk).update(**updates)
        _refresh_sync_states([pk])
    return {
        "galleries": int(gallery),
        "markdown_links": int(links),
        "content_metadata": int(metadata_changed),
    }


def _patch_site_row(website_id, lookup):
    """Lock, re-read and patch one website's metadata. Return True if it changed."""
    with transaction.atomic():
        site = Website.objects.select_for_update().filter(uuid=website_id).first()
        if site is None:
            return False
        metadata, changed = rewrite_json_strings(site.metadata, lookup)
        if changed:
            Website.objects.filter(uuid=website_id).update(metadata=metadata)
    return changed


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

    Backs the dry run's report. The job patches each row itself, see
    _patch_rows.
    """
    if not renames:
        return Followups(metadata=[], markdown=[], site_metadata=[], videos=set())
    lookup = build_path_lookup(
        renames, _site_paths({task.website_id for task in renames})
    )
    own_files = {int(task.pk): (task.old_key, task.new_key) for task in renames}
    return Followups(
        metadata=_collect_content_metadata_patches(lookup, own_files),
        markdown=_collect_markdown_patches(renames, lookup),
        site_metadata=_collect_site_metadata_patches(lookup),
        videos=_linked_videos(renames),
    )


_SYNC_STATE_BATCH = 2000


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
    # Chunked so a large set of pks never builds one UPDATE with a CASE branch
    # per record, or pulls every sync state into memory at once. Postgres does
    # not cap bulk_batch_size.
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


def _current_files(pks):
    """Map each pk in *pks* to the file value its row holds right now."""
    return dict(
        WebsiteContent.objects.filter(pk__in=list(pks)).values_list("pk", "file")
    )


def _delete_old_key(s3, bucket, source_key, stderr):
    """Delete a renamed object's old key. A failure only leaves an orphan."""
    try:
        s3.delete_object(Bucket=bucket, Key=source_key)
    except Exception as exc:  # noqa: BLE001
        # The rename is committed in the database and S3, so the old key is
        # only an orphan now. Warn and keep the success.
        stderr.write(f"Warning: failed to delete old key {source_key}: {exc!s}")


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
        current = _current_files(int(task.pk) for key in batch for task in groups[key])
        for source_key in batch:
            done, errors = _rename_group(
                source_key, groups[source_key], holders, current, s3, stdout, stderr
            )
            committed.extend(done)
            error_count += errors
    return ExecutionResult(committed=committed, error_count=error_count)


def _rename_group(source_key, tasks, holders, current, s3, stdout, stderr):  # noqa: PLR0913, PLR0917
    """
    Rename one source object and every row that points at it.

    Returns (committed tasks, error count). A row already on its new key
    committed in an earlier delivery of this chunk, so its copy is skipped
    and it still counts as committed, which lets its patches run. A row that
    holds neither key was changed after planning, e.g. by a new upload, and
    is left alone. The old key is deleted only when every row committed.
    """
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    target = tasks[0].new_key.lstrip("/")
    committed = [task for task in tasks if current.get(int(task.pk)) == task.new_key]
    pending = [task for task in tasks if current.get(int(task.pk)) == task.old_key]
    for task in tasks:
        if task not in committed and task not in pending:
            stderr.write(_changed_after_planning(task))
    if pending and holders.get(target, set()) - {int(task.pk) for task in tasks}:
        stderr.write(
            f"Error renaming {source_key}: target {target} was taken after "
            "planning. Run the command again to give it a new name."
        )
        pending = []
    if pending:
        try:
            s3.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": source_key},
                Key=target,
                ACL="public-read",
            )
        except Exception as exc:  # noqa: BLE001
            for task in pending:
                stderr.write(
                    f"Error renaming {task.old_key} to {task.new_key}: {exc!s}"
                )
            pending = []
    for task in pending:
        if _commit_row(task, source_key, target, stderr):
            stdout.write(f"Renamed: {task.old_key} -> {task.new_key}")
            committed.append(task)
    if len(committed) < len(tasks):
        stderr.write(f"Keeping {source_key}: not every row was renamed")
        return committed, len(tasks) - len(committed)
    _delete_old_key(s3, bucket, source_key, stderr)
    return committed, 0


def _changed_after_planning(task):
    """Return the error for a row that no longer holds its planned old key."""
    return (
        f"Error renaming {task.old_key}: its row no longer holds that file. "
        "Run the command again to plan it afresh."
    )


def _commit_row(task, source_key, target, stderr):
    """
    Commit one row's rename in its own transaction. Return True on success.

    The update only matches while the row still holds its old key, so a file
    replaced after planning keeps its new value.
    """
    try:
        with transaction.atomic():
            updated = WebsiteContent.objects.filter(
                pk=task.pk, file=task.old_key
            ).update(file=task.new_key)
            if updated:
                DriveFile.objects.filter(resource_id=task.pk, s3_key=source_key).update(
                    s3_key=target
                )
                # Inside the same transaction as the rename it belongs to.
                # Deferring it would leave an interrupted run's committed
                # renames with a stale checksum, and a re-run cannot find
                # them, since they no longer carry a prefix.
                _refresh_sync_states([task.pk])
    except Exception as exc:  # noqa: BLE001
        stderr.write(f"Error renaming {task.old_key} to {task.new_key}: {exc!s}")
        return False
    if not updated:
        stderr.write(_changed_after_planning(task))
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


def _summary(renames, skipped, followups):
    """Build the dry run's line of counts."""
    suffixed = sum(1 for task in renames if task.suffixed)
    shared = len(
        {task.old_key.lstrip("/") for task in renames if _REASON_SHARED in task.reason}
    )
    links = sum(1 for patch in followups.markdown if patch.links)
    galleries = sum(1 for patch in followups.markdown if patch.gallery)
    return ", ".join(
        [
            f"{len(renames) - suffixed} files would be renamed",
            f"{suffixed} files would be renamed with a suffix",
            f"{shared} shared S3 objects",
            f"{skipped} skipped",
            f"{len(followups.metadata)} content metadata records would be patched",
            f"{links} pages with file links would be patched",
            f"{len(followups.site_metadata)} site metadata records would be patched",
            f"{galleries} gallery pages would be patched",
            f"{len(followups.videos)} video pages would be synced again",
        ]
    )


DEFAULT_CHUNK_SIZE = 500

# Integer counts every chunk summary carries, added up by finish_job.
_CHUNK_COUNTS = (
    "renamed",
    "suffixed",
    "errors",
    "content_metadata",
    "markdown_links",
    "galleries",
    "site_metadata",
    "videos",
)


def _selected_contents(website_ids):
    """Return the rows the command considers, limited to *website_ids* if given."""
    contents = (
        WebsiteContent.objects.filter(file__isnull=False)
        .exclude(file="")
        .only("id", "file", "text_id", "website")
    )
    if website_ids is not None:
        contents = contents.filter(website__uuid__in=website_ids)
    return contents


def _referencing_rows(index):
    """
    Find the rows that reference each source object in *index*.

    Returns ({source_key: content pks}, {source_key: website ids}). One scan
    for the whole job, so chunks do not each rescan every website.
    """
    content_refs = defaultdict(set)
    site_refs = defaultdict(set)
    if not index:
        return content_refs, site_refs
    rows = (
        WebsiteContent.objects.annotate(metadata_text=Cast("metadata", TextField()))
        .filter(
            Q(markdown__iregex=_LEGACY_NAME_PATTERN)
            | Q(metadata_text__iregex=_LEGACY_NAME_PATTERN)
        )
        .values_list("pk", "markdown", "metadata")
        .iterator(chunk_size=2000)
    )
    for pk, markdown, metadata in rows:
        entries = referenced_entries(markdown, index) | referenced_entries_in_json(
            metadata, index
        )
        for entry in entries:
            content_refs[index[entry].old_key.lstrip("/")].add(pk)
    sites = (
        Website.objects.annotate(metadata_text=Cast("metadata", TextField()))
        .filter(metadata_text__iregex=_LEGACY_NAME_PATTERN)
        .values_list("uuid", "metadata")
        .iterator(chunk_size=2000)
    )
    for uuid, metadata in sites:
        for entry in referenced_entries_in_json(metadata, index):
            site_refs[index[entry].old_key.lstrip("/")].add(str(uuid))
    return content_refs, site_refs


def plan_job(website_ids, chunk_size):
    """
    Plan the whole run and split it into chunk arguments. Writes nothing.

    Returns (chunks, skipped). Each chunk is (assignments, content_pks,
    website_ids): its exact renames as dicts, and the rows the one reference
    scan found naming those files. A source object and every row pointing at
    it always share a chunk.
    """
    renames, skipped = _collect_renames(_selected_contents(website_ids))
    groups = defaultdict(list)
    for task in renames:
        groups[task.old_key.lstrip("/")].append(task)
    index = build_path_index(
        renames, _site_paths({task.website_id for task in renames})
    )
    content_refs, site_refs = _referencing_rows(index)
    source_keys = list(groups)
    chunks = []
    for start in range(0, len(source_keys), chunk_size):
        keys = source_keys[start : start + chunk_size]
        chunks.append(
            (
                [task._asdict() for key in keys for task in groups[key]],
                sorted({pk for key in keys for pk in content_refs.get(key, ())}),
                sorted({site for key in keys for site in site_refs.get(key, ())}),
            )
        )
    log.info(
        "Rename job planned: %d renames, %d with a suffix, in %d chunks, %d skipped",
        len(renames),
        sum(1 for task in renames if task.suffixed),
        len(chunks),
        skipped,
    )
    return chunks, skipped


class _LogWriter:
    """Let _execute_renames write to the log when it runs inside a task."""

    def __init__(self, level):
        self.level = level

    def write(self, message):
        log.log(self.level, message)


def run_chunk(chunk_id, assignments, content_pks, website_ids):
    """
    Rename and patch one chunk of the plan. Never raises.

    Returns its counts and the renamed websites' names, for the chord
    callback. A task that raised would be acknowledged, never retried,
    and would stop the callback, so failures are counted instead.
    "incomplete" is set when a reference may be left unpatched, which only
    running the chunk again can fix: a renamed file no longer carries a
    UUID, so a later run of the command would not find it.
    """
    started = time.monotonic()
    # Logged before any work, so a chunk that keeps killing its worker, and
    # so never logs a finish, is still identifiable by its id.
    log.info("Rename chunk %s starting: %d renames", chunk_id, len(assignments))
    summary = dict.fromkeys(_CHUNK_COUNTS, 0)
    summary.update(chunk=chunk_id, websites=[], incomplete=False)
    try:
        renames = [RenameTask(**assignment) for assignment in assignments]
        result = _execute_renames(
            renames,
            get_boto3_client("s3"),
            _LogWriter(logging.DEBUG),
            _LogWriter(logging.WARNING),
        )
        # Everything that only needs the renames happens before the patches,
        # so a chunk that fails while patching still leaves its renamed sites
        # flagged and on the list to sync.
        website_uuids = {task.website_id for task in result.committed}
        if website_uuids:
            Website.objects.filter(uuid__in=website_uuids).update(
                has_unpublished_live=True,
                has_unpublished_draft=True,
            )
        videos = _linked_videos(result.committed)
        # A video's own checksum does not change, so clear its synced checksum.
        ContentSyncState.objects.filter(content_id__in=videos).update(
            synced_checksum=None
        )
        suffixed = sum(1 for task in result.committed if task.suffixed)
        summary.update(
            renamed=len(result.committed) - suffixed,
            suffixed=suffixed,
            errors=result.error_count,
            videos=len(videos),
            websites=sorted(
                Website.objects.filter(uuid__in=website_uuids).values_list(
                    "name", flat=True
                )
            ),
        )
        counts = _patch_rows(result.committed, content_pks, website_ids)
        summary.update(
            errors=result.error_count + counts.errors,
            incomplete=counts.errors > 0,
            content_metadata=counts.content_metadata,
            markdown_links=counts.markdown_links,
            galleries=counts.galleries,
            site_metadata=counts.site_metadata,
        )
    except Exception:
        log.exception("Rename chunk %s stopped early", chunk_id)
        summary["errors"] += 1
        summary["incomplete"] = True
    summary["seconds"] = round(time.monotonic() - started, 1)
    log.info(
        "Rename chunk %s finished in %ss: %s", chunk_id, summary["seconds"], summary
    )
    return summary


def finish_job(summaries, skipped, chunk_count):
    """
    Add up the chunk summaries, log the job's line, return (websites, line).

    A chunk delivered twice reports twice and is counted once. With Redis
    that extra report can also run the callback before the last chunk
    reports, so chunks that have not reported are logged.
    """
    by_chunk = {}
    for summary in summaries:
        by_chunk.setdefault(summary.get("chunk"), summary)
    totals = dict.fromkeys(_CHUNK_COUNTS, 0)
    websites = set()
    for summary in by_chunk.values():
        for key in _CHUNK_COUNTS:
            totals[key] += summary.get(key, 0)
        websites.update(summary.get("websites", []))
    missing = sorted(set(range(chunk_count)) - set(by_chunk))
    if missing:
        log.warning(
            "Rename chunks %s had not reported. They may still be running. "
            "Their counts are left out and their websites are not synced.",
            missing,
        )
    incomplete = sorted(
        chunk for chunk, summary in by_chunk.items() if summary.get("incomplete")
    )
    if incomplete:
        log.warning(
            "Rename chunks %s still had errors after their retries. References "
            "to their files may be stale. Their errors are in the log, and the "
            "dry-run CSV maps each file to its new name.",
            incomplete,
        )
    line = (
        f"{totals['renamed']} files renamed, "
        f"{totals['suffixed']} files renamed with a suffix, "
        f"{skipped} skipped, {totals['errors']} errors, "
        f"{totals['content_metadata']} content metadata records patched, "
        f"{totals['markdown_links']} pages with file links patched, "
        f"{totals['site_metadata']} site metadata records patched, "
        f"{totals['galleries']} gallery pages patched, "
        f"{totals['videos']} video pages synced again"
    )
    log.info("Rename job finished: %s", line)
    return sorted(websites), line


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
        parser.add_argument(
            "--chunk-size",
            dest="chunk_size",
            type=int,
            default=DEFAULT_CHUNK_SIZE,
            help="How many S3 objects each background task renames",
        )

    def _selected_website_ids(self):
        """Return the websites --filter/--exclude select, or None for all of them."""
        if not (self.filter_list or self.exclude_list):
            return None
        return [
            str(uuid)
            for uuid in self.filter_websites(Website.objects.all()).values_list(
                "uuid", flat=True
            )
        ]

    def handle(self, *args, **options):
        super().handle(*args, **options)
        website_ids = self._selected_website_ids()
        if website_ids == []:
            msg = "--filter and --exclude selected no websites"
            raise CommandError(msg)
        if options["dry_run"]:
            output_path = options.get("output")
            if not output_path:
                msg = "--output is required when using --dry-run"
                raise CommandError(msg)
            # --- Discovery phase (no S3/DB writes) ---
            renames, skipped_count = _collect_renames(_selected_contents(website_ids))
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
                f"{_summary(renames, skipped_count, followups)}. "
                f"Plan written to {output_path}."
            )
            return

        # --- Execution phase ---
        # Imported here because websites.tasks imports this module.
        from websites.tasks import rename_uuid_files  # noqa: PLC0415

        if options["chunk_size"] < 1:
            msg = "--chunk-size must be at least 1"
            raise CommandError(msg)
        task = rename_uuid_files.delay(
            website_ids, options["chunk_size"], skip_sync=options["skip_sync"]
        )
        self.stdout.write(
            f"Queued rename job {task.id}. The per-chunk and final summaries "
            "are in the Celery worker logs."
        )
