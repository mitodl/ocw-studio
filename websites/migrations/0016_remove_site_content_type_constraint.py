# Generated by Django 3.1 on 2021-03-19 13:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0015_website_starter_config_field"),
    ]

    operations = [
        migrations.AlterField(
            model_name="websitecontent",
            name="type",
            field=models.CharField(max_length=24),
        ),
    ]
