"""
Data migration: back-populate video_captions_resource and video_transcript_resource
from the legacy video_captions_file / video_transcript_file path fields, then remove
those fields.

For each video resource with a scalar path in video_transcript_file, we locate the
corresponding WebsiteContent by matching the file path against WebsiteContent records
with resourcetype=="Document" on the same website.  The Document resourcetype is a
reliable discriminator for transcript PDFs.

For captions, the same path-based lookup is used. The .vtt/.webvtt extension in the
path is a reliable signal; no resourcetype filter is needed.

The _resource fields are written in single-select format for now:
  video_captions_resource   = {"content": "<text_id>", "website": "<name>"}
  video_transcript_resource = {"content": "<text_id>", "website": "<name>"}

Migration 0074 converts these to the multi-select list format used by the relation widget.

The reverse migration looks up each resource by its stored text_id and restores
the original ``_file`` path string.  Only the first text_id is used when the
field holds a list (the old scalar field could only hold one path).
"""

from django.db import migrations


def _find_resource_by_path(WebsiteContent, website, path):
    """Return the WebsiteContent whose file matches *path*, or None.

    Tries the Django FileField first (path stored without leading slash),
    then falls back to metadata["file"] (which may include the leading slash).
    """
    if not path:
        return None
    path_stripped = path.lstrip("/")
    return (
        WebsiteContent.objects.filter(website=website, file=path_stripped).first()
        or WebsiteContent.objects.filter(
            website=website, metadata__file=path
        ).first()
    )


def _backpopulate_resource_fields(apps, schema_editor):
    """Populate _resource fields from legacy _file paths; drop _file fields."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    for content in (
        WebsiteContent.objects.filter(
            metadata__resourcetype="Video", metadata__video_files__isnull=False
        )
        .select_related("website")
        .only("id", "metadata", "website__name")
        .iterator()
    ):
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            continue

        changed = False

        # --- Transcript ---
        # Use resourcetype=Document as the discriminator: PDFs are common across
        # many resource types, but transcript PDFs should be the only Document
        # resources linked to a video.
        transcript_path = video_files.get("video_transcript_file")
        if isinstance(transcript_path, str) and transcript_path:
            resource = (
                WebsiteContent.objects.filter(
                    website=content.website,
                    metadata__resourcetype="Document",
                    file=transcript_path.lstrip("/"),
                ).first()
                or WebsiteContent.objects.filter(
                    website=content.website,
                    metadata__resourcetype="Document",
                    metadata__file=transcript_path,
                ).first()
            )
            if resource:
                video_files["video_transcript_resource"] = {
                    "content": str(resource.text_id),
                    "website": content.website.name,
                }
                changed = True

        # --- Captions ---
        # The .vtt/.webvtt extension in the stored path is a reliable signal;
        # no resourcetype filter is needed.
        captions_path = video_files.get("video_captions_file")
        if isinstance(captions_path, str) and captions_path:
            resource = _find_resource_by_path(
                WebsiteContent, content.website, captions_path
            )
            if resource:
                video_files["video_captions_resource"] = {
                    "content": str(resource.text_id),
                    "website": content.website.name,
                }
                changed = True

        # Only remove a legacy _file field when the resource was successfully
        # linked. Orphan paths (no matching WebsiteContent) are left in place
        # so they can be inspected and remediated rather than silently deleted.
        for resource_field, file_field in (
            ("video_captions_resource", "video_captions_file"),
            ("video_transcript_resource", "video_transcript_file"),
        ):
            if video_files.get(resource_field) and file_field in video_files:
                video_files.pop(file_field)
                changed = True

        if changed:
            content.save(update_fields=["metadata"])


def _reverse_backpopulate(apps, schema_editor):
    """Restore legacy _file path fields from _resource relation fields."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    for content in (
        WebsiteContent.objects.filter(
            metadata__resourcetype="Video", metadata__video_files__isnull=False
        )
        .select_related("website")
        .only("id", "metadata", "website__name")
        .iterator()
    ):
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            continue

        changed = False

        for resource_field, file_field in (
            ("video_captions_resource", "video_captions_file"),
            ("video_transcript_resource", "video_transcript_file"),
        ):
            relation = video_files.pop(resource_field, None)
            if not isinstance(relation, dict):
                continue
            changed = True

            content_val = relation.get("content")
            # content may be a single text_id string or a list; take the first
            if isinstance(content_val, list):
                text_id = content_val[0] if content_val else None
            else:
                text_id = content_val

            if not text_id:
                continue

            resource = (
                WebsiteContent.objects.filter(
                    website=content.website, text_id=text_id
                )
                .only("file", "metadata")
                .first()
            )
            if not resource:
                continue

            # Prefer model FileField; fall back to metadata["file"]
            if resource.file and resource.file.name:
                path = f"/{resource.file.name.lstrip('/')}"
            elif isinstance(resource.metadata, dict) and resource.metadata.get("file"):
                raw = resource.metadata["file"]
                path = f"/{str(raw).lstrip('/')}" if raw else None
            else:
                path = None

            if path:
                video_files[file_field] = path

        if changed:
            content.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0073_migrate_nuclear_topic"),
    ]

    operations = [
        migrations.RunPython(
            _backpopulate_resource_fields,
            reverse_code=_reverse_backpopulate,
        ),
    ]
