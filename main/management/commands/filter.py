"""Filter options for website management commands"""
import json

from django.core.management import BaseCommand
from django.db.models import Q

from content_sync.constants import VERSION_DRAFT
from websites.models import WebsiteContentQuerySet, WebsiteQuerySet


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
        parser.add_argument(
            "-e",
            "--exclude",
            dest="exclude",
            default="",
            help="If specified, exclude website pipelines whose names are in this comma-delimited list",  # noqa: E501
        )

    def handle(self, *args, **options):  # noqa: ARG002
        self.filter_list = []
        filter_sites = options["filter"]
        filter_json = options["filter_json"]
        exclude_sites = options["exclude"]
        if filter_json:
            with open(filter_json) as input_file:  # noqa: PTH123
                self.filter_list = json.load(input_file)
        elif filter_sites:
            self.filter_list = [
                site.strip() for site in filter_sites.split(",") if site
            ]
        if exclude_sites:
            self.exclude_list = [
                site.strip() for site in exclude_sites.split(",") if site
            ]
        if self.filter_list and options["verbosity"] > 1:
            self.stdout.write(f"Filtering by website: {self.filter_list}")
        if self.exclude_list and options["verbosity"] > 1:
            self.stdout.write(f"Excluding websites: {self.exclude_list}")

    def filter_websites(self, websites: WebsiteQuerySet) -> WebsiteQuerySet:
        """Filter websites based on CLI arguments"""
        filtered_websites = websites
        if self.filter_list:
            filtered_websites = filtered_websites.filter(
                Q(name__in=self.filter_list) | Q(short_id__in=self.filter_list)
            )
        if self.exclude_list:
            filtered_websites = filtered_websites.exclude(
                Q(name__in=self.exclude_list) | Q(short_id__in=self.exclude_list)
            )
        return filtered_websites

    def exclude_unpublished_websites(
        self, version: str, websites: WebsiteQuerySet
    ) -> WebsiteQuerySet:
        """Filter websites that are unpublished or have never been published"""
        filtered_websites = websites.filter(unpublish_status__isnull=True)
        if version == VERSION_DRAFT:
            filtered_websites = filtered_websites.exclude(
                draft_publish_date__isnull=True
            )
        else:
            filtered_websites = filtered_websites.exclude(publish_date__isnull=True)
        return filtered_websites

    def filter_website_contents(
        self, website_contents: WebsiteContentQuerySet
    ) -> WebsiteContentQuerySet:
        """Filter website_contents based on CLI arguments."""
        filtered_website_contents = website_contents
        if self.filter_list:
            filtered_website_contents = filtered_website_contents.filter(
                Q(website__name__in=self.filter_list)
                | Q(website__short_id__in=self.filter_list)
            )
        if self.exclude_list:
            filtered_website_contents = filtered_website_contents.exclude(
                Q(website__name__in=self.exclude_list)
                | Q(website__short_id__in=self.exclude_list)
            )
        return filtered_website_contents
