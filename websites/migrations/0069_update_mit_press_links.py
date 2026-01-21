"""
Migration to update Buy at MIT Press links.

Transforms:
  {{% resource_link "UUID" "![Buy at MIT Press](.../mp_logo.gif)" %}}
    -> {{% resource_link "UUID" "Buy at MIT Press" %}}

  WebsiteContent.title (type=external-resource):
    "![Buy at MIT Press](.../mp_logo.gif)" -> "Buy at MIT Press"
"""

import re

from django.db import migrations

from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE

IMAGE_LINK = '![Buy at MIT Press](/images/mp_logo.gif)'
TEXT_LINK = 'Buy at MIT Press'
MP_LOGO_FILTER = 'mp_logo.gif'

RESOURCE_LINK_IMAGE_PATTERN = re.compile(
    r'\{\{% resource_link "([^"]+)" '
    r'"!\[Buy at MIT\s+Press\]\([^)]*mp_logo\.gif\)" %\}\}'
)

RESOURCE_LINK_TEXT_PATTERN = re.compile(
    r'\{\{% resource_link "([^"]+)" "Buy at MIT Press" %\}\}'
)

TITLE_IMAGE_PATTERN = re.compile(
    r'^!\[Buy at MIT\s+Press\]\([^)]*mp_logo\.gif\)$'
)


def update_mit_press_links(apps, schema_editor):
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    markdown_to_update = []
    for content in WebsiteContent.objects.filter(
        markdown__icontains=MP_LOGO_FILTER,
    ):
        updated = RESOURCE_LINK_IMAGE_PATTERN.sub(
            r'{{% resource_link "\1" "' + TEXT_LINK + r'" %}}',
            content.markdown,
        )
        if updated != content.markdown:
            content.markdown = updated
            markdown_to_update.append(content)

    if markdown_to_update:
        WebsiteContent.objects.bulk_update(markdown_to_update, ["markdown"])

    title_to_update = []
    for content in WebsiteContent.objects.filter(
        title__icontains=MP_LOGO_FILTER,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
    ):
        if TITLE_IMAGE_PATTERN.match(content.title):
            content.title = TEXT_LINK
            title_to_update.append(content)

    if title_to_update:
        WebsiteContent.objects.bulk_update(title_to_update, ["title"])


def reverse_mit_press_links(apps, schema_editor):
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    markdown_to_update = []
    for content in WebsiteContent.objects.filter(markdown__icontains=TEXT_LINK):
        updated = RESOURCE_LINK_TEXT_PATTERN.sub(
            r'{{% resource_link "\1" "' + IMAGE_LINK + r'" %}}',
            content.markdown,
        )
        if updated != content.markdown:
            content.markdown = updated
            markdown_to_update.append(content)

    if markdown_to_update:
        WebsiteContent.objects.bulk_update(markdown_to_update, ["markdown"])

    title_to_update = []
    for content in WebsiteContent.objects.filter(
        title=TEXT_LINK,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
    ):
        content.title = IMAGE_LINK
        title_to_update.append(content)

    if title_to_update:
        WebsiteContent.objects.bulk_update(title_to_update, ["title"])


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0068_update_exams_with_solutions_tags"),
    ]

    operations = [
        migrations.RunPython(update_mit_press_links, reverse_mit_press_links),
    ]
