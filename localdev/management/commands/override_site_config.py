""" Overrides locally-stored site configs based on a YAML file in this repo """
import os

import yaml
from django.conf import settings
from django.core.management import BaseCommand

from websites.config_schema.api import validate_parsed_site_config
from websites.constants import COURSE_STARTER_SLUG
from websites.models import WebsiteStarter


DEFAULT_OVERRIDE_CONFIG = "localdev/configs/ocw-course-site-config.yml"
DEFAULT_STARTER_SLUG = COURSE_STARTER_SLUG


class Command(BaseCommand):
    """ Overrides locally-stored site configs based on a YAML file in this repo """

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "-c",
            "--config-path",
            dest="config_path",
            default=DEFAULT_OVERRIDE_CONFIG,
            help="The path to the config file that will be used to overwrite the given WebsiteStarter.",
        )
        parser.add_argument(
            "-s",
            "--starter",
            dest="starter",
            default=DEFAULT_STARTER_SLUG,
            help="The slug value for the WebsiteStarter that the given config will overwrite.",
        )

    def handle(self, *args, **options):
        with open(os.path.join(settings.BASE_DIR, options["config_path"])) as f:
            raw_config = f.read().strip()
        parsed_config = yaml.load(raw_config, Loader=yaml.Loader)
        starter_slug = options["starter"]
        starter = WebsiteStarter.objects.get(slug=starter_slug)
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
