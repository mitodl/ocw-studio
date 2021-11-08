# Generated by Django 3.1.13 on 2021-11-04 18:10

from django.db import migrations

from websites.constants import WEBSITE_SOURCE_STUDIO


def migrate_weights_forward(apps, schema_editor):
    increment_decement_weights(apps, True)


def migrate_weights_backward(apps, schema_editor):
    increment_decement_weights(apps, False)


def increment_decement_weights(apps, forward):
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    weight_change = 10 if forward else -10
    navmenus = WebsiteContent.objects.filter(
        type="navmenu",
        website__source=WEBSITE_SOURCE_STUDIO,
        metadata__leftnav__isnull=False,
    )
    for navmenu in navmenus:
        for menuitem in navmenu.metadata["leftnav"]:
            menuitem["weight"] += weight_change
        navmenu.save()


class Migration(migrations.Migration):

    dependencies = [
        ("websites", "0039_gdrive_sync_progress"),
    ]

    operations = [
        migrations.RunPython(migrate_weights_forward, migrate_weights_backward)
    ]
