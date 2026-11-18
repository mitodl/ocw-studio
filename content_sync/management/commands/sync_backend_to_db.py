"""Syncs a website from a backend (Github, et al) to the database"""  # noqa: INP001

import sys

from django.core.management import CommandError

from content_sync.api import get_sync_backend
from content_sync.management.utils import get_commit_user
from main.management.commands.filter import WebsiteFilterCommand
from websites.api import fetch_website, reset_publishing_fields


class Command(WebsiteFilterCommand):
    """Syncs a website from a backend (Github, et al) to the database"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--user",
            help="Email address of the active Studio user (required with --commit)",
        )
        parser.add_argument(
            "--commit",
            dest="commit",
            help="A particular commit that should be synced.",
            required=False,
        )
        parser.add_argument(
            "--path",
            dest="path",
            help="File or directory to sync. Omit to sync the whole repository.",
            required=False,
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        if not self.filter_list:
            self.stderr.write(
                "You must specify a website or list of websites to process, --filter or --filter-json"  # noqa: E501
            )

        path = options["path"]
        if path is not None:
            path = path.rstrip("/")
        if path == "":
            msg = (
                "--path must name a file or directory. "
                "Omit --path to sync the whole repository."
            )
            raise CommandError(msg)

        commit = options["commit"]
        commit_user = get_commit_user(options["user"]) if commit is not None else None
        confirm = (
            "Y"
            if (path is not None or commit is None)
            else input(
                "Are you sure you want to revert all files for specified sites to this commit? Y/N"  # noqa: E501
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
            content_ids = backend.sync_all_content_to_db(ref=commit, path=path)
            if commit is not None:
                # Sync back to git
                content = (
                    website.websitecontent_set.filter(pk__in=content_ids)
                    if path is not None
                    else None
                )
                backend.sync_all_content_to_backend(
                    query_set=content, commit_user=commit_user
                )
            reset_publishing_fields(website.name)
            self.stdout.write("Completed syncing from backend to database")
