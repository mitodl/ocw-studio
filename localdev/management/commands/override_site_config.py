""" Overrides locally-stored site configs based on a YAML file in this repo """
import os

import yaml
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from websites.config_schema.api import validate_parsed_site_config
from websites.constants import COURSE_STARTER_SLUG, OMNIBUS_STARTER_SLUG
from websites.models import WebsiteStarter


DEFAULT_CONFIG_SLUG_PAIRS = (
    ("localdev/configs/ocw-course-site-config.yml", COURSE_STARTER_SLUG),
    ("localdev/configs/omnibus-site-config.yml", OMNIBUS_STARTER_SLUG),
)
DEFAULT_CONFIG_PATHS = [
    config_slug_pair[0] for config_slug_pair in DEFAULT_CONFIG_SLUG_PAIRS
]
DEFAULT_SLUGS = [config_slug_pair[1] for config_slug_pair in DEFAULT_CONFIG_SLUG_PAIRS]


class Command(BaseCommand):
    """ Overrides locally-stored site configs based on a YAML file in this repo """

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "-c",
            "--config-path",
            dest="config_path",
            action="append",
            default=DEFAULT_CONFIG_PATHS,
            help="The path to the config file that will be used to overwrite the given WebsiteStarter.",
        )
        parser.add_argument(
            "-s",
            "--starter",
            dest="starter",
            action="append",
            default=DEFAULT_SLUGS,
            help="The slug value for the WebsiteStarter that the given config will overwrite.",
        )

    def handle(self, *args, **options):
        config_paths = options["config_path"]
        slugs_to_override = options["starter"]
        if len(config_paths) > len(DEFAULT_CONFIG_PATHS):
            config_paths = config_paths[len(DEFAULT_CONFIG_PATHS) :]
        if len(slugs_to_override) > len(DEFAULT_SLUGS):
            slugs_to_override = slugs_to_override[len(DEFAULT_SLUGS) :]
        if len(config_paths) != len(slugs_to_override):
            raise CommandError(
                "Need to provide the same number of config paths and starter slugs to override "
                f"({len(config_paths)} != {len(slugs_to_override)})"
            )

        for config_path, starter_slug in zip(config_paths, slugs_to_override):
            with open(os.path.join(settings.BASE_DIR, config_path)) as f:
                raw_config = f.read().strip()
            parsed_config = yaml.load(raw_config, Loader=yaml.Loader)
            try:
                starter = WebsiteStarter.objects.get(slug=starter_slug)
            except WebsiteStarter.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"WebsiteStarter with slug '{starter_slug}' not found"
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
