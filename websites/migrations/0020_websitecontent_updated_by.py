# Generated by Django 3.1.6 on 2021-04-15 16:11

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("websites", "0019_text_id_charfield"),
    ]

    operations = [
        migrations.AddField(
            model_name="websitecontent",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="content_updated",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
