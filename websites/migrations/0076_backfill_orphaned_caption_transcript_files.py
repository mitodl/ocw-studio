"""
Data migration: back-populate video_captions_resources / video_transcript_resources
for video resources whose legacy _file path was left orphaned by migration 0074
(no matching WebsiteContent found at the time). Also removes empty-string _file
leftovers from the pre-relation-widget string field, which 0074's falsy-value
guard correctly skipped but never cleaned up.

Two cases handled per video:

1. Empty-string _file value (e.g. video_captions_file == ""): no caption/transcript
   was ever set for this video. The key is simply removed -- there is nothing to
   back-fill.

2. Non-empty orphan _file path: if a WebsiteContent resource already points at
   this exact S3 key (e.g. created by a later sync or manual remediation after
   migration 0074 ran), that resource is reused rather than creating a
   duplicate. Otherwise, the referenced S3 object may still exist even though
   no WebsiteContent record was ever created for it (e.g. content uploaded
   directly to S3 outside of the GDrive/3Play pipelines, using a Google Drive
   file ID as the filename); if so, a new WebsiteContent resource is created
   for it, named after the video's own filename (``{video.filename}_captions``
   / ``{video.filename}_transcript``) rather than the orphan path's filename,
   since the orphan path is often an opaque identifier. If the S3 object no
   longer exists, the _file path is left in place for manual inspection,
   matching migration 0074's philosophy. Either way, the resolved resource's
   id is appended to the resource field's existing ``content`` list without
   dropping an already-linked id, whether that existing value is a list or a
   legacy scalar string.

IMPORTANT: this migration must not run in production until the
`remove_uuid_from_filenames` management command has been run against
production data.

This migration is irreversible: reverse_code is a no-op. Cleanly reversing would
require deleting the WebsiteContent rows this migration creates, which needs a
tracking marker we deliberately don't add.
"""

import uuid

from botocore.exceptions import ClientError
from django.db import migrations

from main.s3_utils import get_boto3_resource

_FIELD_CONFIG = (
    # (file_field, resource_field, filename_suffix, resourcetype)
    ("video_captions_file", "video_captions_resources", "captions", "Other"),
    ("video_transcript_file", "video_transcript_resources", "transcript", "Document"),
)


def _object_exists_in_s3(bucket_name, key):
    """Return True if the S3 object exists."""
    s3 = get_boto3_resource("s3")
    try:
        s3.Object(bucket_name, key).load()
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
    return True


def _unique_filename(WebsiteContent, website, dirpath, base_filename):
    """Return a filename unique within (website, dirpath), suffixing with _2, _3, ... if needed."""
    filename = base_filename
    suffix = 2
    while WebsiteContent.objects.filter(
        website=website, dirpath=dirpath, filename=filename
    ).exists():
        filename = f"{base_filename}_{suffix}"
        suffix += 1
    return filename


def _backfill_orphaned_files(apps, schema_editor):  # noqa: ARG001
    """Clean up empty-string _file leftovers and back-fill real orphaned paths."""
    from django.conf import settings  # noqa: PLC0415

    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    updated_website_ids = set()
    objects_to_update = []

    for content in (
        WebsiteContent.objects.filter(
            metadata__resourcetype="Video", metadata__video_files__isnull=False
        )
        .select_related("website")
        .only("id", "filename", "dirpath", "title", "metadata", "website__name")
        .iterator()
    ):
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            continue

        changed = False

        for file_field, resource_field, suffix, resourcetype in _FIELD_CONFIG:
            path = video_files.get(file_field)
            if not isinstance(path, str):
                continue

            # Case 1: empty-string leftover -- nothing to back-fill, just drop it.
            if not path:
                video_files.pop(file_field)
                changed = True
                continue

            # Case 2: real orphan path. Reuse a resource already pointing at
            # this exact S3 key if one exists (e.g. created by a later sync
            # or manual remediation after migration 0074 ran) instead of
            # creating a duplicate; otherwise verify the object still exists
            # in S3 and create a new resource for it.
            key = path.lstrip("/")
            resource = WebsiteContent.objects.filter(
                website=content.website, file=key
            ).first()
            if resource is None:
                if not _object_exists_in_s3(bucket_name, key):
                    print(  # noqa: T201
                        f"[0076] Skipping missing S3 object for "
                        f"{content.website.name}/{content.filename}: {path}"
                    )
                    continue

                base_filename = f"{content.filename}_{suffix}"
                filename = _unique_filename(
                    WebsiteContent, content.website, content.dirpath, base_filename
                )
                new_text_id = str(uuid.uuid4())
                title = f"{content.title} {suffix}" if content.title else filename
                resource = WebsiteContent.objects.create(
                    website=content.website,
                    type="resource",
                    is_page_content=True,
                    filename=filename,
                    dirpath=content.dirpath,
                    file=key,
                    text_id=new_text_id,
                    title=title,
                    metadata={
                        "file": path,
                        "resourcetype": resourcetype,
                    },
                )

            existing = video_files.get(resource_field)
            existing_ids = []
            if isinstance(existing, dict) and existing.get("content"):
                existing_content = existing["content"]
                existing_ids = (
                    [existing_content]
                    if isinstance(existing_content, str)
                    else list(existing_content)
                )
            resource_text_id = str(resource.text_id)
            if resource_text_id not in existing_ids:
                existing_ids = [*existing_ids, resource_text_id]
            video_files[resource_field] = {
                "content": existing_ids,
                "website": content.website.name,
            }
            video_files.pop(file_field)
            changed = True

        if changed:
            objects_to_update.append(content)
            updated_website_ids.add(content.website_id)

    if objects_to_update:
        WebsiteContent.objects.bulk_update(objects_to_update, ["metadata"])

    if updated_website_ids:
        Website.objects.filter(pk__in=updated_website_ids).update(
            has_unpublished_draft=True,
            has_unpublished_live=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0075_remove_video_file_path_fields"),
    ]

    operations = [
        migrations.RunPython(
            _backfill_orphaned_files,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
