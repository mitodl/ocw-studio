"""Strip control characters (e.g. stray newlines) from external_url values"""  # noqa: INP001

import csv
import re

from django.conf import settings
from mitol.common.utils import now_in_utc

from content_sync.tasks import sync_unsynced_websites
from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.models import WebsiteContent

CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


class Command(WebsiteFilterCommand):
    """Strip control characters (e.g. stray newlines) from external_url values"""

    help = __doc__

    def add_arguments(self, parser):
        """Add command-specific arguments."""
        super().add_arguments(parser)
        parser.add_argument(
            "-o",
            "--out",
            dest="out",
            default=None,
            help="If provided, a CSV file of affected WebsiteContent objects will be written.",  # noqa: E501
        )
        parser.add_argument(
            "-c",
            "--commit",
            dest="commit",
            action="store_true",
            default=False,
            help="Whether the cleaned external_url values should be saved to the database/backend.",  # noqa: E501
        )
        parser.add_argument(
            "-ss",
            "--skip-sync",
            dest="skip_sync",
            action="store_true",
            default=False,
            help="Whether to skip running the sync_unsynced_websites task",
        )

    def handle(self, *args, **options):
        """Find and optionally fix external-resource URLs with control characters."""
        super().handle(*args, **options)
        commit_changes = options["commit"]
        csv_output = options["out"]

        candidates = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_EXTERNAL_RESOURCE
        ).exclude(metadata__external_url__isnull=True)
        candidates = self.filter_website_contents(website_contents=candidates)

        modified_content = []
        for content in candidates.iterator():
            url = content.metadata.get("external_url")
            if not url or not CONTROL_CHAR_RE.search(url):
                continue
            cleaned_url = CONTROL_CHAR_RE.sub("", url)
            modified_content.append(
                {
                    "pk_id": content.pk,
                    "text_id": content.text_id,
                    "website_name": content.website.name,
                    "original_url": url,
                    "cleaned_url": cleaned_url,
                }
            )
            if commit_changes:
                content.metadata["external_url"] = cleaned_url
                content.save()

        self.stdout.write(
            f"Found {len(modified_content)} external-resource(s) with control "
            "characters in external_url"
        )
        self.print_affected_content(modified_content)

        if csv_output and modified_content:
            self.stdout.write(f"Writing affected content to csv file {csv_output}")
            self.write_to_csv(csv_output, modified_content)

        if (
            settings.CONTENT_SYNC_BACKEND
            and commit_changes
            and modified_content
            and not options["skip_sync"]
        ):
            self.stdout.write("Syncing all unsynced content to the designated backend")
            start = now_in_utc()
            task = sync_unsynced_websites.delay(create_backends=True)
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(f"Backend sync finished, took {total_seconds} seconds")

        self.stdout.write(f"Finished with commit={commit_changes}")

    def print_affected_content(self, modified_content: list[dict]):
        """Print affected content to stdout, e.g. to inspect production in a dry run."""
        if not modified_content:
            return
        self.stdout.write("pk_id,text_id,website_name,external_link")
        for content in modified_content:
            self.stdout.write(
                f"{content['pk_id']},{content['text_id']},"
                f"{content['website_name']},{content['original_url']}"
            )

    def write_to_csv(self, path: str, modified_content: list[dict]):
        """Write modified contents to csv."""

        with open(path, "w", newline="") as csvfile:  # noqa: PTH123
            if not modified_content:
                return
            fieldnames = modified_content[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for content in modified_content:
                writer.writerow(content)
