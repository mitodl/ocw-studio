"""
This script defines a Django management command to detect unrelated content in an AWS S3
 bucket for courses.

Usage:
    This command can be run using Django's manage.py:
    `python manage.py detect_unrelated_content`
"""  # noqa: INP001

import json
from tempfile import NamedTemporaryFile

from django.conf import settings

from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_resource
from websites.models import Website, WebsiteContent


class Command(WebsiteFilterCommand):
    """Detect unrelated content in AWS S3 bucket for courses"""

    help = __doc__

    UNRELATED_FILES_THRESHOLD = 100

    def handle(self, *args, **options):
        super().handle(*args, **options)

        website_queryset = self.filter_websites(websites=Website.objects.all())

        s3 = get_boto3_resource("s3")
        unrelated_files = {}
        self.stdout.write(
            self.style.SUCCESS(
                f"Checking for unrelated content in {website_queryset.count()} "
                "websites."
            )
        )

        total_files = 0
        for website in website_queryset:
            files = s3.meta.client.list_objects_v2(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Prefix=f"courses/{website.name}/",
            )
            files_in_s3 = (
                {content["Key"] for content in files.get("Contents", [])}
                if files.get("KeyCount")
                else set()
            )

            website_content_files = set(
                WebsiteContent.objects.filter(
                    website=website, file__in=files_in_s3
                ).values_list("file", flat=True)
            )

            unrelated_website_files = list(files_in_s3 - website_content_files)

            if unrelated_website_files:
                total_files += len(unrelated_website_files)
                unrelated_files[website.name] = unrelated_website_files

        if unrelated_files:
            self.stdout.write(
                self.style.SUCCESS("Unrelated content found in the bucket!")
            )
            content = json.dumps(unrelated_files, indent=4)

            if total_files > self.UNRELATED_FILES_THRESHOLD:
                with NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
                    tmp_file_path = tmp_file.name
                    tmp_file.write(content.encode("utf-8"))
                self.stdout.write(
                    self.style.SUCCESS(
                        "The content has been written to a "
                        f"temporary file located at: {tmp_file_path}"
                    )
                )
            else:
                self.stdout.write(content)

        else:
            self.stdout.write(
                self.style.WARNING("No unrelated content found in the bucket")
            )
