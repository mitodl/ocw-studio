"""Fix malformed external_url values known to break Hugo's Go url.Parse"""  # noqa: INP001

import csv
import re

from django.conf import settings
from mitol.common.utils import now_in_utc

from content_sync.tasks import sync_website_content
from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.models import WebsiteContent

CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
INVALID_PERCENT_ENCODING_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def clean_url(url):
    """
    Apply known-safe corrections to a malformed external_url: strip control
    characters, convert stray backslashes to forward slashes, and trim
    leading/trailing whitespace. Malformed percent-encoding has no safe
    automatic fix, so it's flagged for manual review instead of guessed at.

    Returns (cleaned_url, needs_manual_review).
    """
    cleaned = CONTROL_CHAR_RE.sub("", url)
    cleaned = cleaned.replace("\\", "/")
    cleaned = cleaned.strip()
    needs_manual_review = bool(INVALID_PERCENT_ENCODING_RE.search(cleaned))
    return cleaned, needs_manual_review


class Command(WebsiteFilterCommand):
    """Fix malformed external_url values known to break Hugo's Go url.Parse"""

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
            help="Whether to skip syncing affected websites to the backend",
        )

    def handle(self, *args, **options):
        """Find and optionally fix external-resource URLs known to break Hugo."""
        super().handle(*args, **options)
        commit_changes = options["commit"]
        csv_output = options["out"]

        candidates = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_EXTERNAL_RESOURCE
        ).exclude(metadata__external_url__isnull=True)
        candidates = self.filter_website_contents(website_contents=candidates)

        all_rows = []
        for content in candidates.iterator():
            url = content.metadata.get("external_url")
            if not url:
                continue
            cleaned_url, needs_manual_review = clean_url(url)
            if cleaned_url == url and not needs_manual_review:
                continue
            all_rows.append(
                {
                    "pk_id": content.pk,
                    "text_id": content.text_id,
                    "website_name": content.website.name,
                    "original_url": url,
                    "cleaned_url": cleaned_url,
                    "needs_manual_review": needs_manual_review,
                }
            )
            if cleaned_url != url and commit_changes:
                content.metadata["external_url"] = cleaned_url
                content.save()

        fixed_rows = [
            row for row in all_rows if row["cleaned_url"] != row["original_url"]
        ]
        review_rows = [row for row in all_rows if row["needs_manual_review"]]

        self.stdout.write(
            f"Found {len(fixed_rows)} external-resource(s) that can be "
            f"automatically fixed, and {len(review_rows)} that need manual "
            "review (malformed percent-encoding)"
        )
        self.print_affected_content("Automatically fixed", fixed_rows)
        self.print_affected_content("Needs manual review", review_rows)

        if csv_output and all_rows:
            self.stdout.write(f"Writing affected content to csv file {csv_output}")
            self.write_to_csv(csv_output, all_rows)

        if (
            settings.CONTENT_SYNC_BACKEND
            and commit_changes
            and fixed_rows
            and not options["skip_sync"]
        ):
            website_names = sorted({row["website_name"] for row in fixed_rows})
            self.stdout.write(
                f"Syncing {len(website_names)} affected website(s) to the backend"
            )
            start = now_in_utc()
            for website_name in website_names:
                task = sync_website_content.delay(website_name)
                task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(f"Backend sync finished, took {total_seconds} seconds")

        self.stdout.write(f"Finished with commit={commit_changes}")

    def print_affected_content(self, label: str, rows: list[dict]):
        """Print affected content to stdout, e.g. to inspect production in a dry run."""
        if not rows:
            return
        self.stdout.write(f"{label}:")
        self.stdout.write("pk_id,text_id,website_name,external_link")
        for row in rows:
            self.stdout.write(
                f"{row['pk_id']},{row['text_id']},"
                f"{row['website_name']},{row['original_url']}"
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
