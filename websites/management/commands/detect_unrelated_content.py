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


def list_all_s3_keys(s3_client, bucket, prefix):
    """
    Retrieve all object keys from an S3 bucket using pagination.
    """
    all_keys = set()
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    while True:
        if response.get("Contents"):
            all_keys.update(item["Key"] for item in response["Contents"])
        if response.get("IsTruncated"):
            token = response.get("NextContinuationToken")
            response = s3_client.list_objects_v2(
                Bucket=bucket, Prefix=prefix, ContinuationToken=token
            )
        else:
            break
    return all_keys


class Command(WebsiteFilterCommand):
    """Detect and optionally delete unrelated content in AWS S3 bucket for courses"""

    help = __doc__

    UNRELATED_FILES_THRESHOLD = 100

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--delete", action="store_true", help="Delete unrelated resources from S3"
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        websites = self.filter_websites(websites=Website.objects.all())

        s3 = get_boto3_resource("s3")
        unrelated_files_by_site = {}
        self.stdout.write(
            self.style.SUCCESS(
                f"Checking for unrelated content in {websites.count()} " "websites."
            )
        )

        unrelated_files_count = 0
        for website in websites:
            prefix = f"courses/{website.name}/"
            s3_file_keys = list_all_s3_keys(
                s3.meta.client, settings.AWS_STORAGE_BUCKET_NAME, prefix
            )
            if s3_file_keys:
                website_content_files = WebsiteContent.objects.filter(
                    website=website, file__isnull=False
                ).values_list("file", flat=True)
                normalized_website_content_files = {
                    wc.removeprefix("/") for wc in website_content_files if wc
                }

                unrelated_website_files = list(
                    s3_file_keys - normalized_website_content_files
                )

                if unrelated_website_files:
                    unrelated_files_count += len(unrelated_website_files)
                    unrelated_files_by_site[website.name] = unrelated_website_files

        if unrelated_files_by_site:
            self.stdout.write(
                self.style.SUCCESS("Unrelated content found in the bucket!")
            )
            is_delete = options.get("delete")
            if is_delete:
                deleted_keys = self._delete_unrelated_files(s3, unrelated_files_by_site)
                action = "deleted"
                result_data = deleted_keys
                count = len(deleted_keys)
            else:
                action = "detected"
                result_data = unrelated_files_by_site
                count = unrelated_files_count
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action.capitalize()} {count} unrelated files from S3."
                )
            )
            self._output_result(result_data, count, action)
        else:
            self.stdout.write(
                self.style.WARNING("No unrelated content found in the bucket.")
            )

    def _delete_unrelated_files(self, s3, unrelated_files_by_site):
        """
        Delete objects using S3's delete_objects API.
        Returns a list of keys corresponding to the objects that were deleted.
        """
        all_file_keys = []
        for file_keys in unrelated_files_by_site.values():
            all_file_keys.extend(file_keys)
        deleted_keys = []
        # The API supports up to 1,000 keys per request.
        for i in range(0, len(all_file_keys), 1000):
            chunk = all_file_keys[i : i + 1000]
            objects_to_delete = [{"Key": key} for key in chunk]
            delete_payload = {"Objects": objects_to_delete, "Quiet": False}
            response = s3.meta.client.delete_objects(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Delete=delete_payload,
            )
            deleted_keys.extend(
                item["Key"] for item in response.get("Deleted", []) if "Key" in item
            )
        return deleted_keys

    def _output_result(self, result_data, files_count, action):
        """
        Output the list of unrelated files.
        If the total exceeds UNRELATED_FILES_THRESHOLD,
        write the JSON to a temporary file.
        """
        content = json.dumps(result_data, indent=4)
        if files_count > self.UNRELATED_FILES_THRESHOLD:
            with NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
                tmp_file.write(content.encode("utf-8"))
                tmp_file_path = tmp_file.name
            self.stdout.write(
                self.style.SUCCESS(
                    f"The list of {action} files has been written to a "
                    f"temporary file located at: {tmp_file_path}"
                )
            )
        else:
            self.stdout.write(content)
