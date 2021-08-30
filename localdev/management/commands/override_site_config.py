""" Overrides locally-stored site configs based on a YAML file in this repo """
import os

import yaml
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from websites.config_schema.api import validate_parsed_site_config
from websites.constants import OMNIBUS_STARTER_SLUG
from websites.models import WebsiteStarter


class Command(BaseCommand):
    """ Overrides locally-stored site configs based on a YAML file in this repo """

    help = __doc__

    def _get_pairs(self):
        """
        Get yaml paths and starter slugs.
        Since we are referencing settings we can't populate this until
        Django is initialized, so it has to go inside a function
        """
        return (
            (
                "localdev/configs/ocw-course-site-config.yml",
                settings.OCW_IMPORT_STARTER_SLUG,
            ),
            ("localdev/configs/omnibus-site-config.yml", OMNIBUS_STARTER_SLUG),
        )

    def _get_config_paths(self):
        """Get yaml paths for populating the starters"""
        pairs = self._get_pairs()
        return [config_slug_pair[0] for config_slug_pair in pairs]

    def _get_slugs(self):
        """Get starter slugs"""
        pairs = self._get_pairs()
        return [config_slug_pair[1] for config_slug_pair in pairs]

    def add_arguments(self, parser):

        parser.add_argument(
            "-c",
            "--config-path",
            dest="config_path",
            action="append",
            default=self._get_config_paths(),
            help="The path to the config file that will be used to overwrite the given WebsiteStarter.",
        )
        parser.add_argument(
            "-s",
            "--starter",
            dest="starter",
            action="append",
            default=self._get_slugs(),
            help="The slug value for the WebsiteStarter that the given config will overwrite.",
        )

    def handle(self, *args, **options):
        config_paths = options["config_path"]
        slugs_to_override = options["starter"]
        if len(config_paths) > len(self._get_config_paths()):
            config_paths = config_paths[len(self._get_config_paths()) :]
        if len(slugs_to_override) > len(self._get_slugs()):
            slugs_to_override = slugs_to_override[len(self._get_slugs()) :]
        if len(config_paths) != len(slugs_to_override):
            raise CommandError(
                "Need to provide the same number of config paths and starter slugs to override "
                f"({len(config_paths)} != {len(slugs_to_override)})"
            )

        for config_path, starter_slug in zip(config_paths, slugs_to_override):
            with open(os.path.join(settings.BASE_DIR, config_path)) as f:
                raw_config = f.read().strip()
            parsed_config = yaml.load(raw_config, Loader=yaml.SafeLoader)
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
