# Generated by Django 3.1.6 on 2021-04-23 19:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("websites", "0021_is_page_content_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="websitecontent",
            name="deleted",
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
