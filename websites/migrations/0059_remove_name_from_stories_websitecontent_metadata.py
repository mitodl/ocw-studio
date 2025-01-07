# Manual migration to remove the "name" field from the metadata of existing stories

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def migrate_metadata_forward(apps, schema_editor):
    """
    Forward migration remove the "name" field from the metadata
    of existing stories
    """
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    stories = WebsiteContent.objects.filter(website__name="ocw-www", type="stories")

    for story in stories:
        if story.metadata and "name" in story.metadata:
            del story.metadata["name"]
            story.save(update_fields=["metadata"])


def migrate_metadata_backward(apps, schema_editor):
    """
    Run migration in backward direction.
    This will not return the DB to original state.
    """
    logger.warning(
        "The reverse migration for '0059' of the websites"
        "module cannot restore the original data state."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0058_websitecontent_referencing_content"),
    ]

    operations = [
        migrations.RunPython(migrate_metadata_forward, migrate_metadata_backward),
    ]
