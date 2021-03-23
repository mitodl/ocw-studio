""" Overrides locally-stored site configs based on a YAML file in this repo """
import os

import yaml
from django.conf import settings
from django.core.management import BaseCommand

from websites.config_schema.api import validate_parsed_site_config
from websites.models import WebsiteStarter


LOCAL_STARTERS_DIR = "localdev/starters/"


class Command(BaseCommand):
    """ Overrides locally-stored site configs based on a YAML file in this repo """

    help = __doc__

    def handle(self, *args, **options):
        with open(
            os.path.join(
                settings.BASE_DIR, LOCAL_STARTERS_DIR, "site-config-override.yml"
            )
        ) as f:
            raw_config_override = f.read().strip()
        parsed_config_override = yaml.load(raw_config_override, Loader=yaml.Loader)

        for starter_slug, parsed_config in parsed_config_override.items():
            try:
                starter = WebsiteStarter.objects.get(slug=starter_slug)
            except WebsiteStarter.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"WebsiteStarter with slug {starter_slug} does not exist."
                    )
                )
                continue
            if starter.config != parsed_config:
                validate_parsed_site_config(parsed_config)
                starter.config = parsed_config
                starter.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Config updated for '{starter_slug}' starter.")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No config changes detected for '{starter_slug}' starter."
                    )
                )
