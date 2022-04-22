""" Fix WebsiteContent files that are missing the Website name in their paths"""
import csv
import re
from typing import Dict, List

import boto3
from django.conf import settings
from django.core.management import BaseCommand
from mitol.common.utils import now_in_utc

from content_sync.tasks import sync_unsynced_websites
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.models import WebsiteContent


class Command(BaseCommand):
    """ Fix WebsiteContent files that are missing the Website name in their paths"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--out",
            dest="out",
            default=None,
            help="If provided, a CSV file of WebsiteContent objects with modified paths will be written.",
        )
        parser.add_argument(
            "-c",
            "--commit",
            dest="commit",
            action="store_true",
            default=False,
            help="Whether the changes to WebsiteContent file paths should be saved to the database/backend.",
        )
        parser.add_argument(
            "-p",
            "--prefix",
            dest="prefix",
            default=None,
            help="Prefix string for WebsiteContent query",
            required=True,
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
        commit_changes = options["commit"]
        prefix = options["prefix"]
        csv_output = options["out"]

        modified_content = []
        bad_paths = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_RESOURCE,
            file__regex=r"^/?{}/[A-Za-z0-9\-\.\_]+(\.).*".format(prefix),
        )

        self.stdout.write(
            f"Found {bad_paths.count()} resources with '{prefix}/' file paths missing website names"
        )

        s3_bucket = boto3.resource("s3").Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)
        for content in bad_paths:
            new_path = re.sub(
                r"^(/?{}/)(.*)".format(prefix),
                r"{}/{}/\2".format(prefix, content.website.name),
                content.file.name,
            )
            file_exists = len(list(s3_bucket.objects.filter(Prefix=new_path))) == 1
            content_summary = {
                "website": content.website.name,
                "content": content.text_id,
                "original_path": content.file,
                "new_path": new_path,
                "exists": file_exists,
            }
            if not file_exists:
                self.stderr.write(f"Content not found at new path: {content_summary}.")
            modified_content.append(content_summary)
            if commit_changes and file_exists:
                content.file = new_path
                content.save()

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
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )

        self.stdout.write(f"Finished with commit={commit_changes}")

    def write_to_csv(self, path: str, modified_content: List[Dict]):
        """Write modified contents to csv."""

        with open(path, "w", newline="") as csvfile:
            if not modified_content:
                return
            fieldnames = modified_content[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for content in modified_content:
                writer.writerow(content)
