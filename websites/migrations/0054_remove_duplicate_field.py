# Generated by Django 4.2.13 on 2024-06-20 05:51

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations

from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE

logger = logging.getLogger(__name__)


def is_ocw_domain_url(url: str) -> bool:
    """Return True `url` has an ocw domain."""
    parsed_domain = urlparse(url)
    parsed_ocw_domain = urlparse(settings.STATIC_API_BASE_URL_LIVE)
    return parsed_domain.netloc == parsed_ocw_domain


def migrate_fields_forward(apps, schema_editor):
    """Run migration in forward direction."""
    remove_field_has_external_licence_warning(apps)


def migrate_fields_backward(apps, schema_editor):
    """Run migration in backward direction.
    This will not return the DB to original state.
    """
    logger.warning(
        "The reverse migration for '0054_remove_duplicate_field' cannot restore"
        "the original data state."
    )


def remove_field_has_external_licence_warning(apps):
    """Remove duplicate field from metadata."""
    key = "has_external_licence_warning"
    updated_key = "has_external_license_warning"

    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    resources = WebsiteContent.objects.filter(
        type=CONTENT_TYPE_EXTERNAL_RESOURCE, metadata__has_key=key
    )
    for resource in resources:
        del resource.metadata[key]
        resource.metadata[updated_key] = not is_ocw_domain_url(
            resource.metadata["external_url"]
        )
        resource.save()


class Migration(migrations.Migration):
    """Django migration class."""

    dependencies = [
        ("websites", "0053_safedelete_deleted_by_cascade"),
    ]

    operations = [migrations.RunPython(migrate_fields_forward, migrate_fields_backward)]
