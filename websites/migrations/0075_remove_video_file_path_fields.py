"""
Data migration: convert scalar video_captions_resource and video_transcript_resource
metadata values from single-select to multi-select format, then rename them to
video_captions_resources and video_transcript_resources (plural) to reflect that they
now hold multiple values.

Old (single-select) format written by migration 0074:
  video_files.video_captions_resource   = {"content": "<text_id>", "website": "<name>"}
  video_files.video_transcript_resource = {"content": "<text_id>", "website": "<name>"}

New (multi-select, renamed) format:
  video_files.video_captions_resources  = {"content": ["<text_id>"], "website": "<name>"}
  video_files.video_transcript_resources = {"content": ["<text_id>"], "website": "<name>"}

Records already in list format (content is already a list) are renamed without conversion.

The reverse migration converts lists back to scalars (first element) and renames back
to the singular form. Multi-language content is reduced to its first entry.
"""

from django.db import migrations


_OLD_FIELDS = ("video_captions_resource", "video_transcript_resource")
_NEW_FIELDS = ("video_captions_resources", "video_transcript_resources")


def _convert_and_rename(apps, schema_editor):
    """Convert scalar _resource content to lists and rename fields to plural form."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")

    updated_website_ids = set()

    for content in (
        WebsiteContent.objects.filter(metadata__video_files__isnull=False)
        .only("id", "metadata", "website_id")
        .iterator()
    ):
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            continue

        changed = False

        for old_field, new_field in zip(_OLD_FIELDS, _NEW_FIELDS):
            value = video_files.get(old_field)
            if value is None:
                continue
            if isinstance(value, dict):
                content_val = value.get("content")
                if isinstance(content_val, str) and content_val:
                    value["content"] = [content_val]
            # Rename: move to plural field, remove old key
            video_files[new_field] = value
            del video_files[old_field]
            changed = True

        if changed:
            content.save(update_fields=["metadata"])
            updated_website_ids.add(content.website_id)

    if updated_website_ids:
        Website.objects.filter(pk__in=updated_website_ids).update(
            has_unpublished_draft=True,
            has_unpublished_live=True,
        )


def _reverse_rename_and_convert(apps, schema_editor):
    """Reverse: rename _resources back to _resource and convert lists to scalars."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    for content in (
        WebsiteContent.objects.filter(metadata__video_files__isnull=False)
        .only("id", "metadata")
        .iterator()
    ):
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            continue

        changed = False

        for old_field, new_field in zip(_OLD_FIELDS, _NEW_FIELDS):
            value = video_files.get(new_field)
            if value is None:
                continue
            if isinstance(value, dict):
                content_val = value.get("content")
                if isinstance(content_val, list) and content_val:
                    value["content"] = content_val[0]
            # Rename back: move to singular field, remove plural key
            video_files[old_field] = value
            del video_files[new_field]
            changed = True

        if changed:
            content.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0074_video_caption_transcript_files_to_resources"),
    ]

    operations = [
        migrations.RunPython(
            _convert_and_rename,
            reverse_code=_reverse_rename_and_convert,
        ),
    ]
