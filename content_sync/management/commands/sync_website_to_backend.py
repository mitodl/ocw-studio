"""Syncs a Website and all of its contents to a backend (Github, et al)"""
from django.core.management import BaseCommand

from content_sync.api import get_sync_backend
from content_sync.models import ContentSyncState
from websites.api import fetch_website, reset_publishing_fields


class Command(BaseCommand):
    """Syncs a Website and all of its contents to a backend (Github, et al)"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--website",
            dest="website",
            help="The uuid, name, or title of the Website that should be synced.",
            required=True,
        )
        parser.add_argument(
            "--force-create",
            dest="force_create",
            action="store_true",
            help=(
                "If this flag is added, this command will attempt to create the website in the backend regardless "
                "of whether or not our db records say that it has been synced before."
            ),
        )
        parser.add_argument(
            "--delete",
            dest="git_delete",
            action="store_true",
            help=(
                "If this flag is added, this command will attempt to delete any files in the git repo that do not"
                "match any WebsiteContent filepaths"
            ),
        )

    def handle(self, *args, **options):
        website = fetch_website(options["website"])
        backend = get_sync_backend(website)
        should_create = options["force_create"]
        should_delete = options["git_delete"]
        if not should_create:
            should_create = not ContentSyncState.objects.filter(
                content__website=website
            ).exists()
        if should_create:
            self.stdout.write(f"Creating website in backend for '{website.title}'...")
            backend.create_website_in_backend()
        self.stdout.write(
            f"Updating website content in backend for '{website.title}'..."
        )
        backend.sync_all_content_to_backend(delete=should_delete)
        reset_publishing_fields(website.name)
