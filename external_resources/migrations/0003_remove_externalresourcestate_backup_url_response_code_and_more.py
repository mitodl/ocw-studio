# Generated by Django 4.2.15 on 2024-09-24 10:38

from django.db import migrations, models


def map_status_and_check_failed(apps, schema_editor):
    ExternalResourceState = apps.get_model(
        "external_resources", "ExternalResourceState"
    )
    for state in ExternalResourceState.objects.all():
        if state.status == "broken":
            state.is_broken = True
        elif state.status == "valid":
            state.is_broken = False
        elif state.status == "check_failed":
            state.last_check_failed = True
        state.save(update_fields=["is_broken", "last_check_failed"])


class Migration(migrations.Migration):
    dependencies = [
        ("external_resources", "0002_alter_externalresourcestate_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalresourcestate",
            name="is_broken",
            field=models.BooleanField(
                blank=True,
                default=False,
                help_text="Indicates if the external resource is broken.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="externalresourcestate",
            name="last_check_failed",
            field=models.BooleanField(
                default=False,
                help_text="Indicates whether the last attempt to check for broken links failed.",  # noqa: E501
            ),
        ),
        migrations.AddField(
            model_name="externalresourcestate",
            name="wayback_job_id",
            field=models.CharField(
                blank=True,
                help_text="Job ID returned by Wayback Machine API when submitting URL for snapshot.",  # noqa: E501
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="externalresourcestate",
            name="wayback_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("success", "Success"),
                    ("error", "Error"),
                ],
                default="",
                help_text="The status of the Wayback Machine snapshot taken from archiving job.",  # noqa: E501
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="externalresourcestate",
            name="wayback_url",
            field=models.URLField(
                blank=True, help_text="URL of the Wayback Machine snapshot."
            ),
        ),
        migrations.RunPython(map_status_and_check_failed),
        migrations.RemoveField(
            model_name="externalresourcestate",
            name="backup_url_response_code",
        ),
        migrations.RemoveField(
            model_name="externalresourcestate",
            name="is_backup_url_broken",
        ),
        migrations.RemoveField(
            model_name="externalresourcestate",
            name="is_external_url_broken",
        ),
        migrations.RemoveField(
            model_name="externalresourcestate",
            name="status",
        ),
    ]
