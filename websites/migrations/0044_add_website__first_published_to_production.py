# Generated by Django 3.1.14 on 2022-01-21 14:48

from django.db import migrations, models


def null_out_publish_date_forward(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    websites = Website.objects.all()
    for website in websites:
        website.publish_date = None
        website.save()


def null_out_publish_date_backward(apps, schema_editor):
    """
    no-op, we can't recover this data if we've already
    nulled it out
    """


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0043_remove_website_collections"),
    ]

    operations = [
        migrations.AddField(
            model_name="website",
            name="first_published_to_production",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            null_out_publish_date_forward, null_out_publish_date_backward
        ),
    ]
