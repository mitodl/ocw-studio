"""Syncs a website from a backend (Github, et al) to the database"""
from django.core.management import BaseCommand
from github.GithubObject import NotSet

from content_sync.api import get_sync_backend
from websites.api import fetch_website, reset_publishing_fields
from websites.models import Website


class Command(BaseCommand):
    """Syncs a website from a backend (Github, et al) to the database"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--website",
            dest="website",
            help="The uuid, name, or title of the Website that should be synced.",
            required=True,
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
            help="A particular git filepath that should be synced.",
            required=False,
        )

    def handle(self, *args, **options):
        website = fetch_website(options["website"])
        commit = options["commit"] or NotSet
        path = options["path"]
        confirm = (
            "Y"
            if (path is not None or commit is NotSet)
            else input(
                "Are you sure you want to revert all files for this site to the specified commit? Y/N"
            ).upper()
        )
        if confirm != "Y":
            exit(0)
        backend = get_sync_backend(website)
        self.stdout.write(
            f"Syncing content from backend to database for '{website.title}'..."
        )
        backend.sync_all_content_to_db(ref=commit, path=path)
        if commit is not NotSet:
            # Sync back to git
            backend.sync_all_content_to_backend()
        reset_publishing_fields(website.name)
        self.stdout.write(f"Completed syncing from backend to database")
