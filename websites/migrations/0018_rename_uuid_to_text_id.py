# Generated by Django 3.1.6 on 2021-04-15 01:40

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0017_rename_filepath"),
    ]

    operations = [
        migrations.RenameField(
            model_name="websitecontent",
            old_name="uuid",
            new_name="text_id",
        ),
        migrations.AlterUniqueTogether(
            name="websitecontent",
            unique_together={("website", "text_id")},
        ),
    ]
