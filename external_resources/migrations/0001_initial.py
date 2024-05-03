# Generated by Django 4.2.11 on 2024-05-02 09:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("websites", "0053_safedelete_deleted_by_cascade"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalResourceState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("unchecked", "Unchecked or pending check"),
                            ("valid", "Either URL or backup URL is valid"),
                            ("broken", "Both URL and backup URL are broken"),
                        ],
                        default="unchecked",
                        help_text="The status of this external resource.",
                        max_length=16,
                    ),
                ),
                (
                    "external_url_response_code",
                    models.IntegerField(blank=True, default=None, null=True),
                ),
                (
                    "backup_url_response_code",
                    models.IntegerField(blank=True, default=None, null=True),
                ),
                (
                    "is_external_url_broken",
                    models.BooleanField(blank=True, default=None, null=True),
                ),
                (
                    "is_backup_url_broken",
                    models.BooleanField(blank=True, default=None, null=True),
                ),
                (
                    "last_checked",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="The last time when this resource"
                        " was checked for breakages.",
                        null=True,
                    ),
                ),
                (
                    "content",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="external_resource_state",
                        to="websites.websitecontent",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
