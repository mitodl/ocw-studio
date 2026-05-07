"""Update visibility for all repos in the configured GitLab group"""  # noqa: INP001

from django.core.management.base import BaseCommand

from content_sync.apis.gitlab import update_all_repos_visibility


class Command(BaseCommand):
    """Update visibility for all repos in the configured GitLab group"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--visibility",
            dest="visibility",
            default="public",
            help="Target visibility for all repos (default: public)",
        )
        parser.add_argument(
            "--yes",
            dest="yes",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *_args, **options):
        visibility = options["visibility"]
        if not options["yes"]:
            confirmation = input(
                f"WARNING: This will update ALL repos in the GitLab group to "
                f"'{visibility}'. Proceed? (y/n): "
            )
            if confirmation.strip().lower() != "y":
                self.stdout.write("Aborting.")
                return

        self.stdout.write(f"Updating all repos to visibility='{visibility}'...")
        count = update_all_repos_visibility(visibility=visibility)
        self.stdout.write(f"Done. Updated {count} repo(s).")
