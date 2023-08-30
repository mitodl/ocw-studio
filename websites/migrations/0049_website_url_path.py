# Generated by Django 3.1.14 on 2022-05-12 18:40

from django.db import migrations, models

from websites.site_config_api import SiteConfig


def populate_url_path(apps, schema_editor):
    """
    Populate url_path for all sites that have already been published to production
    """
    Website = apps.get_model("websites", "Website")
    for site in Website.objects.exclude(publish_date__isnull=True):
        if site.starter is None:
            continue
        site_config = SiteConfig(site.starter.config)
        root = site_config.root_url_path
        site.url_path = f"{root}/{site.name}".strip("/")
        site.save()


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0048_www_pages_to_page"),
    ]

    operations = [
        migrations.AddField(
            model_name="website",
            name="url_path",
            field=models.CharField(max_length=2048, null=True, blank=True, unique=True),
        ),
        migrations.RunPython(populate_url_path, migrations.RunPython.noop),
    ]
