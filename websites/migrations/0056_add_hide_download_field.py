# Generated by Django 4.2.13 on 2024-07-31 12:25

import logging

from django.db import migrations, transaction
from django.db.models import Q

from websites.constants import CONTENT_TYPE_WEBSITE

logger = logging.getLogger(__name__)


def migrate_fields_forward(apps, schema_editor):
    """Run migration in forward direction."""

    HIDE_DOWNLOAD_FLAG = "hide_download"

    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    contents = WebsiteContent.objects.filter(
        Q(type=CONTENT_TYPE_WEBSITE) & ~Q(metadata__has_key=HIDE_DOWNLOAD_FLAG)
    )

    with transaction.atomic():
        for content in contents:
            content.metadata[HIDE_DOWNLOAD_FLAG] = False
            content.save()


def migrate_fields_backward(apps, schema_editor):
    """Run migration in backward direction.
    This will not return the DB to original state.
    """
    logger.warning(
        "The reverse migration for '0056_add_hide_download_field' cannot restore"
        "the original data state."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0055_alter_website_has_unpublished_draft_and_more"),
    ]

    operations = [migrations.RunPython(migrate_fields_forward, migrate_fields_backward)]