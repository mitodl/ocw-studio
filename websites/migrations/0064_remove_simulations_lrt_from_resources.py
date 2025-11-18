"""Remove Simulations learning resource type from resource-level content."""

from django.db import migrations, transaction

SIMULATIONS_LRT = "Simulations"


def remove_simulations_lrt_from_resources(apps, schema_editor):
    """Remove 'Simulations' from learning_resource_types for resource content only."""
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
        if isinstance(lrts, list) and SIMULATIONS_LRT in lrts:
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


class Migration(migrations.Migration):
    """Remove Simulations LRT from resources."""

    dependencies = [
        ("websites", "0063_alter_website_latest_build_id_draft_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_simulations_lrt_from_resources,
            restore_simulations_lrt_to_resources,
        ),
    ]
