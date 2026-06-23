"""Remove legacy UUID prefixes from resource filenames in S3."""  # noqa: INP001

import csv
import re
import sys
from collections import Counter
from typing import NamedTuple

from django.conf import settings

from gdrive_sync.models import DriveFile
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_client
from websites.models import Website, WebsiteContent


class RenameTask(NamedTuple):
    """A planned S3 + DB rename for one WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    website_id: str  # str(Website.uuid) — UUID FK used for dirty-flag bulk update
    old_key: str
    new_key: str


class MetadataPatch(NamedTuple):
    """A planned metadata update for one Video-type WebsiteContent record."""

    pk: str  # str(WebsiteContent.pk) — integer AutoField stringified
    updated_metadata: dict


UUID_FILENAME_RE = re.compile(r"^[0-9a-f]{32}_", re.IGNORECASE)


def strip_uuid_prefix(path):
    """
    Strip a UUID prefix from the basename of a path value.

    Handles values stored with or without a leading slash.
    Returns the original value unchanged if no UUID prefix is found or if
    stripping would leave an empty basename.
    """
    stripped = path.lstrip("/")
    lead = path[: len(path) - len(stripped)]  # "" or "/"
    prefix_path, _, basename = stripped.rpartition("/")
    if not UUID_FILENAME_RE.match(basename):
        return path
    new_basename = basename[33:]  # 32 hex chars + 1 underscore
    if not new_basename:
        return path
    new_path = f"{prefix_path}/{new_basename}" if prefix_path else new_basename
    return f"{lead}{new_path}"


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
    # Normalize keys to strip any leading slash so conflict detection works
    # regardless of whether legacy content stores paths with or without one.
    existing_files = {
        f.lstrip("/"): pk
        for f, pk in WebsiteContent.objects.exclude(file="").values_list("file", "pk")
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

        candidates.append((content.pk, str(content.website_id), old_key, new_key))

    # Pass 2: find target keys claimed by more than one source — ALL must be skipped.
    # Normalize with lstrip to catch collisions between slash-prefixed and non-prefixed
    # variants that resolve to the same S3 key.
    target_counts = Counter(new_key.lstrip("/") for _, _, _, new_key in candidates)

    # Pass 3: build the final task list, dropping ambiguous and conflicting targets.
    tasks = []
    for pk, website_id, old_key, new_key in candidates:
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
            help=(
                "File path for the dry-run CSV plan (default: stdout). "
                "Only used with --dry-run."
            ),
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
            output_path = options.get("output")
            if output_path:
                with open(output_path, "w", newline="") as f:  # noqa: PTH123
                    _write_csv_rows(
                        csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES),
                        renames,
                        website_names,
                    )
                plan_dest = output_path
            else:
                _write_csv_rows(
                    csv.DictWriter(self.stdout, fieldnames=_CSV_FIELDNAMES),
                    renames,
                    website_names,
                )
                plan_dest = "stdout"
            self.stdout.write(
                f"Dry run complete: {len(renames)} files would be renamed, "
                f"{skipped_count} skipped, "
                f"{len(planned_patches)} video metadata records would be patched. "
                f"Plan written to {plan_dest}."
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
                WebsiteContent.objects.filter(pk=task.pk).update(file=task.new_key)
                DriveFile.objects.filter(resource_id=task.pk, s3_key=s3_old_key).update(
                    s3_key=s3_new_key
                )
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

        self.stdout.write(
            f"Done: {renamed_count} renamed, {skipped_count} skipped, "
            f"{error_count} errors, {len(patches)} video metadata records patched"
        )
