"""Syncs a website from a backend (Github, et al) to the database"""
import sys

from github.GithubObject import NotSet

from content_sync.api import get_sync_backend
from main.management.commands.filter import WebsiteFilterCommand
from websites.api import fetch_website, reset_publishing_fields


class Command(WebsiteFilterCommand):
    """Syncs a website from a backend (Github, et al) to the database"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--commit",
            dest="commit",
            help="A particular commit that should be synced.",
            required=False,
        )
        parser.add_argument(
            "--path",
            dest="path",
            help="A particular git filepath that should be synced.",
            required=False,
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        if not self.filter_list:
            self.stdout.stderr(
                "You must specify a website or list of websites to process, --filter or --filter-json"
            )

        commit = options["commit"] or NotSet
        path = options["path"]
        confirm = (
            "Y"
            if (path is not None or commit is NotSet)
            else input(
                "Are you sure you want to revert all files for specified sites to this commit? Y/N"
            ).upper()
        )
        if confirm != "Y":
            sys.exit(0)
        for site_identifier in self.filter_list:
            website = fetch_website(site_identifier)
            backend = get_sync_backend(website)
            self.stdout.write(
                f"Syncing content from backend to database for '{website.title}'..."
            )
            backend.sync_all_content_to_db(ref=commit, path=path)
            if commit is not NotSet:
                # Sync back to git
                backend.sync_all_content_to_backend()
            reset_publishing_fields(website.name)
            self.stdout.write("Completed syncing from backend to database")
