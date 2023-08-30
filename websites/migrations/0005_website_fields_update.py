# Generated by Django 3.1 on 2021-02-03 17:52

from django.db import migrations, models, transaction
from django.db.models import Count

COURSE_STARTER_SLUG = "course"
WEBSITE_SOURCE_OCW_IMPORT = "ocw-import"


def set_website_source_and_starter(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    WebsiteStarter = apps.get_model("websites", "WebsiteStarter")
    course_starter = WebsiteStarter.objects.filter(slug=COURSE_STARTER_SLUG).first()
    if course_starter is None:
        return
    with transaction.atomic():
        Website.objects.select_for_update().filter(type=COURSE_STARTER_SLUG).update(
            source=WEBSITE_SOURCE_OCW_IMPORT, starter_id=course_starter.id
        )


def set_website_type(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    with transaction.atomic():
        Website.objects.select_for_update().filter(
            source=WEBSITE_SOURCE_OCW_IMPORT
        ).update(type=COURSE_STARTER_SLUG)


def populate_empty_names(apps, schema_editor):
    """
    Fetches all Websites with empty/duplicate 'name' values and sets those values to something we know will be
    unique. That way, reintroducing the unique constraint on the field will not fail.
    """  # noqa: E501, D401
    Website = apps.get_model("websites", "Website")
    # Set the 'name' for all records with an empty 'name' value
    for website in Website.objects.filter(name=None):
        # Set the 'name' value to the uuid, which we know will be unique
        website.name = website.uuid
        website.save()
    # Set the 'name' for all records with a duplicate 'name' value
    duplicate_name_results = (
        Website.objects.values("name")
        .annotate(count=Count("uuid"))
        .values("name")
        .order_by()
        .filter(count__gt=1)
    )
    for duplicate_name_result in duplicate_name_results:
        websites = Website.objects.filter(name=duplicate_name_result["name"])
        if websites.count() <= 1:
            continue
        dupe_name_websites = websites[1:]
        for website in dupe_name_websites:
            # Set the 'name' value to the uuid, which we know will be unique
            website.name = website.uuid
            website.save()


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0004_websitestarter_slug"),
    ]

    operations = [
        migrations.RenameField(
            model_name="website",
            old_name="url_path",
            new_name="name",
        ),
        migrations.AlterField(
            model_name="website",
            name="name",
            field=models.CharField(
                blank=True, db_index=True, max_length=512, null=True
            ),
        ),
        migrations.RunPython(populate_empty_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="website",
            name="name",
            field=models.CharField(db_index=True, max_length=512, unique=True),
        ),
        migrations.AddField(
            model_name="website",
            name="source",
            field=models.CharField(
                blank=True,
                choices=[("studio", "studio"), ("ocw-import", "ocw-import")],
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(set_website_source_and_starter, set_website_type),
        migrations.RemoveField(
            model_name="website",
            name="type",
        ),
    ]
