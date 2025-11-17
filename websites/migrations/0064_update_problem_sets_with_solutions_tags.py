"""Migration to update Problem Set Solutions tags."""

from django.db import migrations, transaction

PROBLEM_SETS_WITH_SOLUTIONS = "Problem Sets with Solutions"
PROBLEM_SETS = "Problem Sets"
PROBLEM_SET_SOLUTIONS = "Problem Set Solutions"


def update_problem_sets_tags(apps, schema_editor):
    """
    Update Website and WebsiteContent items tagged with "Problem Set Solutions".

    Adds both "Problem Sets" and "Problem Set Solutions" tags to items
    that have "Problem Sets with Solutions", then removes "Problem Sets with Solutions".
    """
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    with transaction.atomic():
        websites_to_update = Website.objects.filter(
            metadata__learning_resource_types__contains=[PROBLEM_SETS_WITH_SOLUTIONS]
        )
        contents_to_update = WebsiteContent.objects.filter(
            metadata__learning_resource_types__contains=[PROBLEM_SETS_WITH_SOLUTIONS]
        )

        update_learning_resource_types(websites_to_update)
        update_learning_resource_types(contents_to_update)


def update_learning_resource_types(items):
    """Update learning_resource_types for the given items."""
    for item in items.iterator():
        metadata = item.metadata or {}
        learning_resource_types = metadata.get("learning_resource_types", [])

        # Add "Problem Sets" if not already present
        if PROBLEM_SETS not in learning_resource_types:
            learning_resource_types.append(PROBLEM_SETS)

        # Add "Problem Set Solutions" if not already present
        if PROBLEM_SET_SOLUTIONS not in learning_resource_types:
            learning_resource_types.append(PROBLEM_SET_SOLUTIONS)

        # Remove "Problem Sets with Solutions"
        learning_resource_types.remove(PROBLEM_SETS_WITH_SOLUTIONS)

        metadata["learning_resource_types"] = learning_resource_types
        item.metadata = metadata
        item.save(update_fields=["metadata"])


def reverse_problem_sets_tags(apps, schema_editor):
    """
    Reverse the migration by restoring the original "Problem Sets with Solutions" tag.
    """
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    with transaction.atomic():
        websites_to_update = Website.objects.filter(
            metadata__learning_resource_types__contains=[
                PROBLEM_SETS,
                PROBLEM_SET_SOLUTIONS,
            ]
        ).exclude(
            metadata__learning_resource_types__contains=[PROBLEM_SETS_WITH_SOLUTIONS]
        )
        contents_to_update = WebsiteContent.objects.filter(
            metadata__learning_resource_types__contains=[
                PROBLEM_SETS,
                PROBLEM_SET_SOLUTIONS
            ]
        ).exclude(
            metadata__learning_resource_types__contains=[PROBLEM_SETS_WITH_SOLUTIONS]
        )

        restore_learning_resource_types(websites_to_update)
        restore_learning_resource_types(contents_to_update)


def restore_learning_resource_types(items):
    """Restore the original learning_resource_types for the given items."""
    for item in items.iterator():
        metadata = item.metadata or {}
        learning_resource_types = metadata.get("learning_resource_types", [])

        # Add "Problem Sets with Solutions" back
        if PROBLEM_SETS_WITH_SOLUTIONS not in learning_resource_types:
            learning_resource_types.append(PROBLEM_SETS_WITH_SOLUTIONS)

        # Remove "Problem Sets" and "Problem Set Solutions"
        if PROBLEM_SETS in learning_resource_types:
            learning_resource_types.remove(PROBLEM_SETS)
        if PROBLEM_SET_SOLUTIONS in learning_resource_types:
            learning_resource_types.remove(PROBLEM_SET_SOLUTIONS)

        metadata["learning_resource_types"] = learning_resource_types
        item.metadata = metadata
        item.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    """Migration to update Problem Set Solutions tags."""

    dependencies = [
        ("websites", "0063_alter_website_latest_build_id_draft_and_more"),
    ]

    operations = [
        migrations.RunPython(
            update_problem_sets_tags,
            reverse_problem_sets_tags,
        ),
    ]
