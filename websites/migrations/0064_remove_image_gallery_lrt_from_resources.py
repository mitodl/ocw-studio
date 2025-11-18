"""Remove Image Gallery learning resource type from resource-level content."""

from django.db import migrations, transaction

IMAGE_GALLERY_LRT = "Image Gallery"


def remove_image_gallery_lrt_from_resources(apps, schema_editor):
    """Remove 'Image Gallery' from learning_resource_types for resource content only."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    with transaction.atomic():
        resources_to_update = WebsiteContent.objects.filter(
            metadata__learning_resource_types__contains=IMAGE_GALLERY_LRT,
        ).exclude(type__in=["sitemetadata", "website"])

        for resource in resources_to_update.iterator():
            metadata = resource.metadata or {}
            lrts = metadata.get("learning_resource_types")
            if isinstance(lrts, list) and IMAGE_GALLERY_LRT in lrts:
                lrts.remove(IMAGE_GALLERY_LRT)
                metadata["learning_resource_types"] = lrts
                resource.metadata = metadata
                resource.save(update_fields=["metadata"])


def restore_image_gallery_lrt_to_resources(apps, schema_editor):
    """
    No-op reverse migration.

    Cannot reliably determine which resources originally had 'Image Gallery'
    in their learning_resource_types.
    """


class Migration(migrations.Migration):
    """Remove Image Gallery LRT from resources."""

    dependencies = [
        ("websites", "0063_alter_website_latest_build_id_draft_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_image_gallery_lrt_from_resources,
            restore_image_gallery_lrt_to_resources,
        ),
    ]
