# Generated by Django 4.2.15 on 2024-10-14 17:56

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0057_website_draft_build_date_website_live_build_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="websitecontent",
            name="referencing_pages",
            field=models.ManyToManyField(
                blank=True,
                symmetrical=False,
                help_text="Pages that reference this content.",
                related_name="referenced_by",
                to="websites.websitecontent",
            ),
        ),
    ]
