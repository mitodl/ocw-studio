# Data migration to add referencing content for existing resources

import logging

from django.db import migrations

from websites.utils import compile_referencing_content

logger = logging.getLogger(__name__)


def migrate_metadata_forward(apps, schema_editor):
    """
    Forward migration remove the "name" field from the metadata
    of existing stories
    """
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    website_content = WebsiteContent.objects.all()

    for content in website_content:
        if references := compile_referencing_content(content):
            references = WebsiteContent.objects.filter(text_id__in=references)
            content.referenced_by.set(references)
            content.save()


def migrate_metadata_backward(apps, schema_editor):
    """
    Run migration in backward direction.
    This will not return the DB to original state.
    """
    logger.warning(
        "Backward migration for adding referencing content is not implemented. "
        "This will not return the DB to original state."
    )


class Migration(migrations.Migration):
    """Data migration to add referencing content for existing resources"""

    dependencies = [
        ("websites", "0059_remove_name_from_stories_websitecontent_metadata"),
    ]

    operations = [
        migrations.RunPython(migrate_metadata_forward, migrate_metadata_backward),
    ]
