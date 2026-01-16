"""Migration to update Exams with Solutions tags."""

from django.db import migrations

OLD_TAG = "Exams with Solutions"
NEW_TAGS = ["Exams", "Exam Solutions"]


def update_tags(apps, schema_editor):
    """Replace 'Exams with Solutions' with 'Exams' and 'Exam Solutions'."""
    for model in ["Website", "WebsiteContent"]:
        Model = apps.get_model("websites", model)
        for item in Model.objects.filter(
            metadata__learning_resource_types__contains=[OLD_TAG]
        ).iterator():
            types = item.metadata.get("learning_resource_types", [])
            types.remove(OLD_TAG)
            types.extend(tag for tag in NEW_TAGS if tag not in types)
            item.metadata["learning_resource_types"] = types
            item.save(update_fields=["metadata"])


def reverse_tags(apps, schema_editor):
    """Restore 'Exams with Solutions' from 'Exams' and 'Exam Solutions'."""
    for model in ["Website", "WebsiteContent"]:
        Model = apps.get_model("websites", model)
        for item in Model.objects.filter(
            metadata__learning_resource_types__contains=NEW_TAGS
        ).exclude(
            metadata__learning_resource_types__contains=[OLD_TAG]
        ).iterator():
            types = item.metadata.get("learning_resource_types", [])
            for tag in NEW_TAGS:
                if tag in types:
                    types.remove(tag)
            types.append(OLD_TAG)
            item.metadata["learning_resource_types"] = types
            item.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    """Migration to update Exams with Solutions tags."""

    dependencies = [
        ("websites", "0067_delete_mit_fields_starter"),
    ]

    operations = [
        migrations.RunPython(update_tags, reverse_tags),
    ]
