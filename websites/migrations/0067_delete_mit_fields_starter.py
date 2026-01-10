"""Delete the mit-fields WebsiteStarter"""

from django.db import migrations


def delete_mit_fields_starter(apps, schema_editor):
    """Delete the mit-fields WebsiteStarter"""
    WebsiteStarter = apps.get_model("websites", "WebsiteStarter")
    WebsiteStarter.objects.filter(slug="mit-fields").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0066_remove_simulations_lrt_from_resources"),
    ]

    operations = [
        migrations.RunPython(delete_mit_fields_starter, migrations.RunPython.noop),
    ]
