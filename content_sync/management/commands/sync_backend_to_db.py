"""Syncs a website from a backend (Github, et al) to the database"""
from django.core.management import BaseCommand

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

    def handle(self, *args, **options):
        website = fetch_website(options["website"])
        backend = get_sync_backend(website)
        self.stdout.write(
            f"Syncing content from backend to database for '{website.title}'..."
        )
        backend.sync_all_content_to_db()
        reset_publishing_fields(website.name)
        self.stdout.write(f"Completed syncing from backend to database")
