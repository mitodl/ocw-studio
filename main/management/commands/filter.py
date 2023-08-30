"""Filter options for website management commands"""
import json

from django.core.management import BaseCommand
from django.db.models import Q

from websites.models import WebsiteContentQuerySet


class WebsiteFilterCommand(BaseCommand):
    """Common options for filtering by Website"""

    filter_list = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--filter-json",
            dest="filter_json",
            default=None,
            help="If specified, only publish courses that contain comma-delimited site names specified in a JSON file",  # noqa: E501
        )
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only trigger website pipelines whose names are in this comma-delimited list",  # noqa: E501
        )

    def handle(self, *args, **options):  # noqa: ARG002
        self.filter_list = []
        filter_json = options["filter_json"]
        if filter_json:
            with open(filter_json) as input_file:  # noqa: PTH123
                self.filter_list = json.load(input_file)
        else:
            self.filter_list = [
                site.strip() for site in options["filter"].split(",") if site
            ]
        if self.filter_list and options["verbosity"] > 1:
            self.stdout.write(f"Filtering by website: {self.filter_list}")

    def filter_website_contents(
        self, website_contents: WebsiteContentQuerySet
    ) -> WebsiteContentQuerySet:
        """Filter website_contents based on CLI arguments."""
        if not self.filter_list:
            return website_contents
        return website_contents.filter(
            Q(website__name__in=self.filter_list)
            | Q(website__short_id__in=self.filter_list)
        )
