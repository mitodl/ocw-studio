"""Manual migration to update learning resource types in metadata."""

import logging

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

# Mapping of old learning resource types to new ones
LEARNING_RESOURCE_TYPE_MAPPING = {
    "Exam Materials": "Supplemental Exam Materials",
    "Labs": "Laboratory Assignments",
    "Music": "Music Audio",
    "Online Textbook": "Open Textbooks",
    "Recitation Videos": "Problem-solving Videos",
    "Recitation Notes": "Problem-solving Notes",
}


def update_learning_resource_types_in_metadata(learning_types):
    """Update learning resource types according to the mapping."""
    updated_types = []
    has_changes = False

    for resource_type in learning_types:
        if resource_type in LEARNING_RESOURCE_TYPE_MAPPING:
            updated_types.append(LEARNING_RESOURCE_TYPE_MAPPING[resource_type])
            has_changes = True
        else:
            updated_types.append(resource_type)

    return updated_types, has_changes


def migrate_learning_resource_types_forward(apps, schema_editor):
    """
    Forward migration to update learning_resource_types in metadata.
    """
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")

    updated_count = 0
    total_processed = 0

    with transaction.atomic():
        # Update WebsiteContent objects
        contents_with_learning_types = WebsiteContent.objects.filter(
            metadata__has_key="learning_resource_types"
        )

        for content in contents_with_learning_types:
            total_processed += 1
            learning_types = content.metadata.get("learning_resource_types", [])

            if not isinstance(learning_types, list):
                continue

            updated_types, has_changes = update_learning_resource_types_in_metadata(
                learning_types
            )

            if has_changes:
                content.metadata["learning_resource_types"] = updated_types
                content.save(update_fields=["metadata"])
                updated_count += 1

        # Update Website objects
        websites_with_learning_types = Website.objects.filter(
            metadata__has_key="learning_resource_types"
        )

        for website in websites_with_learning_types:
            total_processed += 1
            learning_types = website.metadata.get("learning_resource_types", [])

            if not isinstance(learning_types, list):
                continue

            updated_types, has_changes = update_learning_resource_types_in_metadata(
                learning_types
            )

            if has_changes:
                website.metadata["learning_resource_types"] = updated_types
                website.save(update_fields=["metadata"])
                updated_count += 1
                logger.info(
                    "Updated learning resource types for Website %s",
                    website.name,
                )

    logger.info(
        "Migration complete. Processed %s objects, "
        "updated %s objects with learning resource type changes.",
        total_processed,
        updated_count,
    )


def restore_learning_resource_types_in_metadata(learning_types, reverse_mapping):
    """Restore learning resource types to their original values."""
    restored_types = []
    has_changes = False

    for resource_type in learning_types:
        if resource_type in reverse_mapping:
            restored_types.append(reverse_mapping[resource_type])
            has_changes = True
        else:
            restored_types.append(resource_type)

    return restored_types, has_changes


def migrate_learning_resource_types_backward(apps, schema_editor):
    """
    Reverse migration to restore original learning_resource_types in metadata.
    """
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")

    # Create reverse mapping
    reverse_mapping = {v: k for k, v in LEARNING_RESOURCE_TYPE_MAPPING.items()}

    updated_count = 0
    total_processed = 0

    with transaction.atomic():
        # Restore WebsiteContent objects
        contents_with_learning_types = WebsiteContent.objects.filter(
            metadata__has_key="learning_resource_types"
        )

        for content in contents_with_learning_types:
            total_processed += 1
            learning_types = content.metadata.get("learning_resource_types", [])

            if not isinstance(learning_types, list):
                continue

            restored_types, has_changes = restore_learning_resource_types_in_metadata(
                learning_types, reverse_mapping
            )

            if has_changes:
                content.metadata["learning_resource_types"] = restored_types
                content.save(update_fields=["metadata"])
                updated_count += 1
                website_name = content.website.name if content.website else "Unknown"
                logger.info(
                    "Restored learning resource types for WebsiteContent %s "
                    "(website: %s)",
                    content.id,
                    website_name,
                )

        # Restore Website objects
        websites_with_learning_types = Website.objects.filter(
            metadata__has_key="learning_resource_types"
        )

        for website in websites_with_learning_types:
            total_processed += 1
            learning_types = website.metadata.get("learning_resource_types", [])

            if not isinstance(learning_types, list):
                continue

            restored_types, has_changes = restore_learning_resource_types_in_metadata(
                learning_types, reverse_mapping
            )

            if has_changes:
                website.metadata["learning_resource_types"] = restored_types
                website.save(update_fields=["metadata"])
                updated_count += 1
                logger.info(
                    "Restored learning resource types for Website %s",
                    website.name,
                )

    logger.info(
        "Reverse migration complete. Processed %s objects, "
        "restored %s objects with learning resource type changes.",
        total_processed,
        updated_count,
    )


class Migration(migrations.Migration):
    """Migration to update learning resource types in metadata."""

    dependencies = [
        ("websites", "0060_add_referencing_content_for_existing_resources"),
    ]

    operations = [
        migrations.RunPython(
            migrate_learning_resource_types_forward,
            migrate_learning_resource_types_backward,
        ),
    ]
