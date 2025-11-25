"""
Remove `Simulations` learning resource type from resource and course
level content.
"""

import logging

from django.db import migrations, transaction

SIMULATIONS_LRT = "Simulations"

logger = logging.getLogger(__name__)


def remove_simulations_lrt_from_resources(apps, schema_editor):
    """
    Remove 'Simulations' from learning_resource_types for resource and course
    levels.
    """
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    with transaction.atomic():
        websites_to_update = Website.objects.filter(
            metadata__learning_resource_types__contains=SIMULATIONS_LRT,
        )
        resources_to_update = WebsiteContent.objects.filter(
            metadata__learning_resource_types__contains=SIMULATIONS_LRT,
        )

        update_learning_resource_types(websites_to_update)
        update_learning_resource_types(resources_to_update)


def update_learning_resource_types(items):
    """Update learning_resource_types for the given items."""

    for resource in items.iterator():
        metadata = resource.metadata or {}
        lrts = metadata.get("learning_resource_types")
        if isinstance(lrts, list):
            lrts.remove(SIMULATIONS_LRT)
            metadata["learning_resource_types"] = lrts
            resource.metadata = metadata
            resource.save(update_fields=["metadata"])


def restore_simulations_lrt_to_resources(apps, schema_editor):
    """
    No-op reverse migration.

    Cannot reliably determine which resources originally had 'Simulations'
    in their learning_resource_types.
    """

    logger.warning(
        "Backward migration for adding `Simulations` LRT is not implemented. "
        "This will not return the DB to original state."
    )


class Migration(migrations.Migration):
    """Remove Simulations LRT from resources."""

    dependencies = [
        ("websites", "0065_remove_image_gallery_lrt_from_resources"),
    ]

    operations = [
        migrations.RunPython(
            remove_simulations_lrt_from_resources,
            restore_simulations_lrt_to_resources,
        ),
    ]
