# Generated by Django 3.1.12 on 2021-08-10 20:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("videos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="videofile",
            name="destination_status",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="videofile",
            name="status",
            field=models.CharField(default="Created", max_length=50),
        ),
        migrations.AlterField(
            model_name="videojob",
            name="status",
            field=models.CharField(default="Created", max_length=50),
        ),
    ]
