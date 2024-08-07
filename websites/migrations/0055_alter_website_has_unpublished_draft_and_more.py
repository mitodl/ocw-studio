# Generated by Django 4.2.13 on 2024-07-31 12:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0054_remove_duplicate_field"),
    ]

    operations = [
        migrations.AlterField(
            model_name="website",
            name="has_unpublished_draft",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="website",
            name="has_unpublished_live",
            field=models.BooleanField(default=False),
        ),
    ]
