from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def create_default_robots_txt(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Url = apps.get_model("robots", "Url")
    Rule = apps.get_model("robots", "Rule")

    domain = urlparse(settings.SITE_BASE_URL).netloc

    # django.contrib.sites should be creating this, but it's in a delayed post-migration hook:
    #
    current_site, created = Site.objects.get_or_create(
        pk=getattr(settings, "SITE_ID", 1), defaults=dict(domain=domain, name=domain)
    )

    url, _ = Url.objects.get_or_create(pattern="/")

    rule, created = Rule.objects.get_or_create(robot="*")

    if created:
        rule.sites.add(current_site)
        rule.disallowed.add(url)
        rule.save()


class Migration(migrations.Migration):

    dependencies = [("sites", "0002_alter_domain_unique"), ("robots", "0001_initial")]

    operations = [
        migrations.RunPython(create_default_robots_txt, migrations.RunPython.noop)
    ]
