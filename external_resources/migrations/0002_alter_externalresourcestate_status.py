# Generated by Django 4.2.11 on 2024-05-03 11:39

from django.db import migrations, models


class Migration(migrations.Migration):
    """Django Migration for External Resources"""

    dependencies = [
        ("external_resources", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externalresourcestate",
            name="status",
            field=models.CharField(
                choices=[
                    ("unchecked", "Unchecked or pending check"),
                    ("valid", "Either URL or backup URL is valid"),
                    ("broken", "Both URL and backup URL are broken"),
                    (
                        "check_failed",
                        "Last attempt to check the resource failed unexpectedly",
                    ),
                ],
                default="unchecked",
                help_text="The status of this external resource.",
                max_length=16,
            ),
        ),
    ]
