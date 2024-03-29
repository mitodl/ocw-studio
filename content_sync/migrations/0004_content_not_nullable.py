# Generated by Django 3.1.6 on 2021-04-29 14:31

import django.db.models.deletion
from django.db import migrations, models


def remove_null_content(apps, schema_editor):
    """Remove ContentSyncStates where content is None"""
    ContentSyncState = apps.get_model("content_sync", "ContentSyncState")
    ContentSyncState.objects.filter(content=None).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0022_website_content_safedelete"),
        ("content_sync", "0003_content_sync_state_nullable_content"),
    ]

    operations = [
        migrations.RunPython(remove_null_content, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contentsyncstate",
            name="content",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="content_sync_state",
                to="websites.websitecontent",
            ),
        ),
    ]
