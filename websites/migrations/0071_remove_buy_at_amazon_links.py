"""
Remove Buy at Amazon links from markdown and
hard-delete their associated external resources.
"""

import logging
import re

from django.db import migrations, transaction
from safedelete.models import HARD_DELETE

from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE

logger = logging.getLogger(__name__)

AMAZON_BUTTON_IMAGE = "a_logo_17.gif"

AMAZON_BUTTON_SHORTCODE_PATTERN = re.compile(
    r'\{\{% resource_link "[^"]+" "!\[[^\]]*\]\(/images/a_logo_17\.gif\)" %\}\} ?'
)
AMAZON_BUTTON_IMAGE_PATTERN = re.compile(r'!\[[^\]]*\]\(/images/a_logo_17\.gif\) ?')
AMAZON_BUTTON_TITLE_PATTERN = re.compile(r"^!\[[^\]]*\]\(/images/a_logo_17\.gif\)$")


def remove_amazon_links(apps, schema_editor):  # noqa: ARG001
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    markdown_to_update = []
    for content in WebsiteContent.objects.filter(markdown__icontains=AMAZON_BUTTON_IMAGE):
        updated = AMAZON_BUTTON_SHORTCODE_PATTERN.sub("", content.markdown)
        updated = AMAZON_BUTTON_IMAGE_PATTERN.sub("", updated)
        if updated != content.markdown:
            content.markdown = updated
            markdown_to_update.append(content)

    resources_to_delete = [
        content
        for content in WebsiteContent.objects.filter(
            title__icontains=AMAZON_BUTTON_IMAGE,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        )
        if AMAZON_BUTTON_TITLE_PATTERN.match(content.title)
    ]

    with transaction.atomic():
        if markdown_to_update:
            WebsiteContent.objects.bulk_update(markdown_to_update, ["markdown"])

        for content in resources_to_delete:
            content.delete(force_policy=HARD_DELETE)


def reverse_remove_amazon_links(apps, schema_editor):  # noqa: ARG001
    """
    Run migration in backward direction.
    This will not return the DB to original state.
    """
    logger.warning("Migration is not reversible; removed Amazon links cannot be restored.")


class Migration(migrations.Migration):
    dependencies = [
        (
            "external_resources",
            "0003_remove_externalresourcestate_backup_url_response_code_and_more",
        ),
        ("websites", "0070_website_site_type"),
    ]

    operations = [
        migrations.RunPython(remove_amazon_links, reverse_remove_amazon_links),
    ]
