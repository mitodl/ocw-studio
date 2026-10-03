"""Syncs a Website and all of its contents to a backend (Github, et al)"""  # noqa: INP001

from content_sync.api import get_sync_backend
from content_sync.management.utils import get_commit_user
from content_sync.models import ContentSyncState
from main.management.commands.filter import WebsiteFilterCommand
from websites.api import fetch_website, reset_publishing_fields


class Command(WebsiteFilterCommand):
    """Syncs a Website and all of its contents to a backend (Github, et al)"""

    help = __doc__

    def add_arguments(self, parser):
        """Add the operator identity and backend sync options."""
        super().add_arguments(parser)
        parser.add_argument(
            "--user",
            required=True,
            help="Email address of the active Studio user performing this sync",
        )
        parser.add_argument(
            "--force-create",
            dest="force_create",
            action="store_true",
            help=(
                "If this flag is added, this command will attempt to create the website in the backend regardless "  # noqa: E501
                "of whether or not our db records say that it has been synced before."
            ),
        )
        parser.add_argument(
            "--delete",
            dest="git_delete",
            action="store_true",
            help=(
                "If this flag is added, this command will attempt to delete any files in the git repo that do not"  # noqa: E501
                "match any WebsiteContent filepaths"
            ),
        )

    def handle(self, *args, **options):
        """Sync the requested websites using the given user's commit identity."""
        super().handle(*args, **options)
        commit_user = get_commit_user(options["user"])
        if not self.filter_list:
            self.stderr.write(
                "You must specify a website or list of websites to process, --filter or --filter-json"  # noqa: E501
            )
        for site_identifier in self.filter_list:
            website = fetch_website(site_identifier)
            if (
                website.name in self.exclude_list
                or website.short_id in self.exclude_list
            ):
                continue
            backend = get_sync_backend(website)
            should_create = options["force_create"]
            should_delete = options["git_delete"]
            if not should_create:
                should_create = not ContentSyncState.objects.filter(
                    content__website=website
                ).exists()
            if should_create:
                self.stdout.write(
                    f"Creating website in backend for '{website.title}'..."
                )
                backend.create_website_in_backend()
            self.stdout.write(
                f"Updating website content in backend for '{website.title}'..."
            )
            backend.sync_all_content_to_backend(commit_user=commit_user)
            if should_delete:
                backend.delete_orphaned_content_in_backend(commit_user=commit_user)
            reset_publishing_fields(website.name)
