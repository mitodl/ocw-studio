"""Remove legacy UUID prefixes from resource filenames in S3."""  # noqa: INP001

import csv
import sys
from collections import Counter
from typing import NamedTuple

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from gdrive_sync.models import DriveFile
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_client
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.rules.gallery_image_rename import (
    GALLERY_ITEM_SHORTCODE_NAME,
    BaseGalleryHrefRewriteRule,
)
from websites.models import Website, WebsiteContent
from websites.utils import UUID_FILENAME_RE, strip_uuid_prefix


class RenameTask(NamedTuple):
    """A planned S3 + DB rename for one WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    website_id: str  # str(Website.uuid) — UUID FK used for dirty-flag bulk update
    text_id: str  # WebsiteContent.text_id — what a gallery item's uuid param names
    old_key: str
    new_key: str


class MetadataPatch(NamedTuple):
    """A planned metadata update for one Video-type WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    updated_metadata: dict


class MarkdownPatch(NamedTuple):
    """A planned markdown update for one WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    updated_markdown: str


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
        if uuid:
            new_basename = self.uuid_map.get(site, {}).get(uuid)
            if new_basename is not None:
                # Already correct, so nothing to rewrite.
                return None if new_basename == href else new_basename
        return self.basename_map.get(site, {}).get(href)


def _collect_renames(queryset):
    """
    Scan *queryset* for WebsiteContent records whose file basename has a UUID
    prefix and return the planned renames.

    Returns (tasks, skipped_count) where:
      tasks         -- list of RenameTask, one per valid rename
      skipped_count -- number of records skipped due to empty-result or conflict

    When multiple UUID-prefixed files would resolve to the same target key,
    ALL of them are skipped — not just the second-and-later. This prevents a
    collision where one source renames successfully but the other sources are
    left with UUID prefixes still pointing at conflicting paths.

    Pre-fetches all existing file→pk mappings once upfront so the per-record
    conflict check is an O(1) dict lookup rather than an individual DB query.
    """
    skipped = 0
    # Restrict conflict detection to the websites present in the queryset.
    # S3 keys are namespaced by website name, so cross-website collisions
    # are impossible and scanning the whole table is wasteful at scale.
    website_ids = set(queryset.values_list("website_id", flat=True).distinct())
    existing_files = {
        f.lstrip("/"): pk
        for f, pk in WebsiteContent.objects.filter(website_id__in=website_ids)
        .exclude(file="")
        .values_list("file", "pk")
        if f
    }

    # Pass 1: collect all candidates that have a strippable UUID prefix.
    candidates = []
    for content in queryset.iterator():
        old_key = str(content.file)
        new_key = strip_uuid_prefix(old_key)

        if new_key == old_key:
            # Either no UUID prefix, or strip would leave empty basename.
            # Distinguish: re-check the basename directly.
            _, _, basename = old_key.rpartition("/")
            if UUID_FILENAME_RE.match(basename) and not basename[33:]:
                print(  # noqa: T201
                    f"Skipping {old_key}: filename would be empty after removing UUID prefix",  # noqa: E501
                    file=sys.stderr,
                )
                skipped += 1
            continue

        candidates.append(
            (content.pk, str(content.website_id), content.text_id, old_key, new_key)
        )

    # Pass 2: find target keys claimed by more than one source — ALL must be skipped.
    # Normalize with lstrip to catch collisions between slash-prefixed and non-prefixed
    # variants that resolve to the same S3 key.
    target_counts = Counter(new_key.lstrip("/") for *_, new_key in candidates)

    # Pass 3: build the final task list, dropping ambiguous and conflicting targets.
    tasks = []
    for pk, website_id, text_id, old_key, new_key in candidates:
        norm_new = new_key.lstrip("/")
        if target_counts[norm_new] > 1:
            print(  # noqa: T201
                f"Skipping {old_key}: target key {new_key} is claimed by {target_counts[norm_new]} sources",  # noqa: E501
                file=sys.stderr,
            )
            skipped += 1
            continue

        conflicting_pk = existing_files.get(norm_new)
        if conflicting_pk and conflicting_pk != pk:
            print(  # noqa: T201
                f"Skipping {old_key}: target key {new_key} already used by content pk={conflicting_pk}",  # noqa: E501
                file=sys.stderr,
            )
            skipped += 1
            continue

        tasks.append(
            RenameTask(
                pk=str(pk),
                website_id=website_id,
                text_id=str(text_id),
                old_key=old_key,
                new_key=new_key,
            )
        )
    return tasks, skipped


def _collect_metadata_patches(website_uuids, renamed_keys=None):
    """
    Scan Video-type resource records in *website_uuids* for stale UUID-prefixed
    paths in metadata["video_files"]["video_captions_file"] and
    ["video_transcript_file"].

    Returns list[MetadataPatch] — one entry per record that needs updating.
    Does not write to the database.

    *renamed_keys* — if provided, only patch metadata values whose path
    (after stripping a leading slash) appears in this set. This prevents
    patching video metadata for a captions/transcript file whose rename was
    skipped (e.g. due to a conflict), which would otherwise leave the metadata
    pointing at the wrong S3 path. Omit for dry-run paths where all planned
    renames are assumed to succeed.
    """
    if not website_uuids:
        return []

    patches = []
    video_resources = (
        WebsiteContent.objects.filter(
            website__uuid__in=website_uuids,
            type="resource",
            metadata__resourcetype="Video",
            metadata__video_files__isnull=False,
        )
        .values("pk", "metadata")
        .iterator()
    )
    for resource in video_resources:
        metadata = resource["metadata"] or {}
        vf = metadata.get("video_files") or {}
        changed = False
        for field in ("video_captions_file", "video_transcript_file"):
            val = vf.get(field) or ""
            if val:
                # If a renamed_keys filter is provided, skip values whose
                # underlying file was not actually renamed (e.g. skipped due
                # to a conflict). lstrip handles leading-slash variants.
                if renamed_keys is not None and val.lstrip("/") not in renamed_keys:
                    continue
                new_val = strip_uuid_prefix(val)
                if new_val != val:
                    vf[field] = new_val
                    changed = True
        if changed:
            metadata["video_files"] = vf
            patches.append(
                MetadataPatch(pk=str(resource["pk"]), updated_metadata=metadata)
            )
    return patches


def _collect_gallery_patches(renames):
    """
    Scan gallery markdown in the same websites as *renames* for
    image-gallery-item shortcodes whose href matches an old basename from
    this run's rename plan, and compute the patched markdown.

    Returns list[MarkdownPatch]. Does not write to the database. Works
    identically whether or not the underlying file renames have already been
    applied to WebsiteContent.file, since matching is driven entirely by the
    *renames* plan already computed by _collect_renames — not by querying
    live WebsiteContent.file state. This lets the same function back both
    the --dry-run preview and the live-run patch.

    A single record whose markdown contains a malformed shortcode (invalid
    Hugo syntax elsewhere on the page, unrelated to the gallery item itself)
    is skipped with a stderr warning rather than aborting the whole scan —
    legacy-imported markdown across tens of thousands of pages can't be
    assumed to all parse cleanly, and one bad page must not cost every other
    page in the batch its gallery-href fix.
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
        WebsiteContent.objects.filter(website__uuid__in=basename_map.keys())
        .filter(markdown__contains=GALLERY_ITEM_SHORTCODE_NAME)
        .exclude(markdown="")
        .iterator()
    )
    patches = []
    for wc in contents:
        try:
            changed = cleaner.update_website_content(wc)
        except Exception as exc:  # noqa: BLE001
            print(  # noqa: T201
                f"Skipping gallery-href scan for content pk={wc.pk}: {exc!s}",
                file=sys.stderr,
            )
            continue
        if changed:
            patches.append(MarkdownPatch(pk=str(wc.pk), updated_markdown=wc.markdown))
        # Discard per-match bookkeeping the cleaner isn't asked to report here
        # (no CSV export in this path) — otherwise it grows unboundedly across
        # a large scan, holding a reference to every scanned WebsiteContent.
        cleaner.replacement_matches.clear()
    return patches


_CSV_FIELDNAMES = ["pk", "website_id", "website_name", "old_key", "new_key"]


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
            }
        )


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
            # Compute planned patches only for the dry-run summary count.
            planned_patches = _collect_metadata_patches(planned_website_ids)
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
            # Write the CSV rename plan before scanning gallery markdown: the
            # plan is the operator's safety artifact and must not depend on
            # markdown parsing succeeding. _collect_gallery_patches guards
            # per-record internally, but this ordering means even an
            # unanticipated failure there can't cost the CSV export.
            with open(output_path, "w", newline="", encoding="utf-8") as f:  # noqa: PTH123
                _write_csv_rows(
                    csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES),
                    renames,
                    website_names,
                )
            planned_gallery_patches = _collect_gallery_patches(renames)
            self.stdout.write(
                f"Dry run complete: {len(renames)} files would be renamed, "
                f"{skipped_count} skipped, "
                f"{len(planned_patches)} video metadata records would be patched, "
                f"{len(planned_gallery_patches)} gallery pages would be patched. "
                f"Plan written to {output_path}."
            )
            return

        # --- Execution phase ---
        s3 = get_boto3_client("s3")
        renamed_count = 0
        error_count = 0
        actually_renamed_website_ids = set()
        successfully_renamed_old_keys: set[str] = set()

        for task in renames:
            # Legacy content.file values may be stored with a leading slash
            # (e.g. /courses/...) but S3 keys never start with /.  Normalize
            # before S3 operations to avoid NoSuchKey on pre-sites/ content.
            s3_old_key = task.old_key.lstrip("/")
            s3_new_key = task.new_key.lstrip("/")
            try:
                s3.copy_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    CopySource={
                        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                        "Key": s3_old_key,
                    },
                    Key=s3_new_key,
                    ACL="public-read",
                )
                with transaction.atomic():
                    WebsiteContent.objects.filter(pk=task.pk).update(file=task.new_key)
                    DriveFile.objects.filter(
                        resource_id=task.pk, s3_key=s3_old_key
                    ).update(s3_key=s3_new_key)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    f"Error renaming {task.old_key} to {task.new_key}: {exc!s}"
                )
                error_count += 1
                continue

            # copy + DB updates committed — record success for dirty-flag and
            # metadata patching regardless of whether the old-key cleanup below
            # succeeds.
            self.stdout.write(f"Renamed: {task.old_key} -> {task.new_key}")
            renamed_count += 1
            actually_renamed_website_ids.add(task.website_id)
            # Store normalized key so _collect_metadata_patches can match
            # val.lstrip("/") against it regardless of slash format.
            successfully_renamed_old_keys.add(s3_old_key)

            try:
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=s3_old_key,
                )
            except Exception as exc:  # noqa: BLE001
                # The rename is already committed in DB and S3; the old key is
                # now an orphan.  Log a warning but keep the success counters.
                self.stderr.write(
                    f"Warning: failed to delete old key {s3_old_key}: {exc!s}"
                )

        # Dirty-flag and metadata updates are scoped to websites where at least
        # one rename actually committed to the DB — not the full planned set.
        # This prevents marking websites dirty or patching video metadata when
        # the underlying S3/DB rename failed.
        if actually_renamed_website_ids:
            Website.objects.filter(uuid__in=actually_renamed_website_ids).update(
                has_unpublished_live=True,
                has_unpublished_draft=True,
            )

        # Pass successfully_renamed_old_keys so metadata is only patched for
        # captions/transcript files whose underlying rename actually committed.
        # Skipped files (e.g. due to a conflict) are excluded, preventing
        # metadata from pointing at the wrong S3 path.
        patches = _collect_metadata_patches(
            actually_renamed_website_ids,
            renamed_keys=successfully_renamed_old_keys,
        )
        if patches:
            WebsiteContent.objects.bulk_update(
                [
                    WebsiteContent(pk=patch.pk, metadata=patch.updated_metadata)
                    for patch in patches
                ],
                ["metadata"],
            )

        # Same exclusion rationale as the metadata patches above: only rewrite
        # gallery hrefs for renames that actually committed.
        successful_renames = [
            task
            for task in renames
            if task.old_key.lstrip("/") in successfully_renamed_old_keys
        ]
        gallery_patches = _collect_gallery_patches(successful_renames)
        if gallery_patches:
            WebsiteContent.objects.bulk_update(
                [
                    WebsiteContent(pk=patch.pk, markdown=patch.updated_markdown)
                    for patch in gallery_patches
                ],
                ["markdown"],
            )

        self.stdout.write(
            f"Done: {renamed_count} renamed, {skipped_count} skipped, "
            f"{error_count} errors, {len(patches)} video metadata records patched, "
            f"{len(gallery_patches)} gallery pages patched"
        )
