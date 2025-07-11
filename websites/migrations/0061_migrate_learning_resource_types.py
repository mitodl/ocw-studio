"""Manual migration to update learning resource types in metadata."""

from django.db import migrations, transaction
from django.db.models import Q

# Mapping of old learning resource types to new ones
LEARNING_RESOURCE_TYPE_MAPPING = {
    "Exam Materials": "Supplemental Exam Materials",
    "Labs": "Laboratory Assignments",
    "Music": "Music Audio",
    "Online Textbook": "Open Textbooks",
    "Recitation Videos": "Problem-solving Videos",
    "Recitation Notes": "Problem-solving Notes",
}


def apply_mapping_to_types(learning_types, mapping):
    """Apply mapping to learning resource types in place."""
    if not isinstance(learning_types, list):
        return False

    has_changes = False
    for i, resource_type in enumerate(learning_types):
        if resource_type in mapping:
            learning_types[i] = mapping[resource_type]
            has_changes = True

    return has_changes


def update_website_content_objects(mapping, WebsiteContent):
    """Update learning_resource_types in WebsiteContent objects."""

    # Build query for objects containing any of the target values
    query = Q()
    for old_type in mapping:
        query |= Q(metadata__learning_resource_types__contains=old_type)

    queryset = WebsiteContent.objects.filter(query)

    for content in queryset:
        learning_types = content.metadata.get("learning_resource_types", [])
        has_changes = apply_mapping_to_types(learning_types, mapping)

        if has_changes:
            content.metadata["learning_resource_types"] = learning_types
            content.save(update_fields=["metadata"])


def update_website_objects(mapping, Website):
    """Update learning_resource_types in Website objects."""

    # Build query for objects containing any of the target values
    query = Q()
    for old_type in mapping:
        query |= Q(metadata__learning_resource_types__contains=old_type)

    queryset = Website.objects.filter(query)

    for website in queryset:
        learning_types = website.metadata.get("learning_resource_types", [])
        has_changes = apply_mapping_to_types(learning_types, mapping)

        if has_changes:
            website.metadata["learning_resource_types"] = learning_types
            website.save(update_fields=["metadata"])


def update_learning_resource_types(mapping, apps):
    """Update learning_resource_types in metadata using the provided mapping."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")

    with transaction.atomic():
        update_website_content_objects(mapping, WebsiteContent)
        update_website_objects(mapping, Website)


def migrate_learning_resource_types_forward(apps, schema_editor):
    """Forward migration to update learning_resource_types in metadata."""
    update_learning_resource_types(LEARNING_RESOURCE_TYPE_MAPPING, apps)


def migrate_learning_resource_types_backward(apps, schema_editor):
    """Reverse migration to restore original learning_resource_types."""
    # Create reverse mapping
    reverse_mapping = {v: k for k, v in LEARNING_RESOURCE_TYPE_MAPPING.items()}
    update_learning_resource_types(reverse_mapping, apps)


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
