from django.db import migrations


def convert_to_resource(apps, schema_editor):
    """
    Convert file to resource in WebsiteContent
    """
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    WebsiteContent.objects.filter(type="file").update(type="resource")


def convert_to_file(apps, schema_editor):
    """
    Convert resource to file in WebsiteContent
    """
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    WebsiteContent.objects.filter(type="resource").update(type="file")


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0008_site_permissions"),
    ]

    operations = [
        migrations.RunPython(convert_to_resource, convert_to_file),
    ]
