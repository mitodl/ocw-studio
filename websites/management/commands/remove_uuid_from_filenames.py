"""Remove legacy UUID prefixes from resource filenames in S3."""  # noqa: INP001

import re

from django.conf import settings

from gdrive_sync.models import DriveFile
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_client
from websites.models import WebsiteContent

UUID_FILENAME_RE = re.compile(r"^[0-9a-f]{32}_", re.IGNORECASE)


class Command(WebsiteFilterCommand):
    """Remove legacy UUID prefixes from resource filenames in S3 and update database records."""  # noqa: E501

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Print what would be done without making any changes",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        dry_run = options["dry_run"]
        s3 = get_boto3_client("s3")

        contents = self.filter_website_contents(
            WebsiteContent.objects.filter(file__isnull=False).exclude(file="")
        )

        renamed_count = 0
        skipped_count = 0
        error_count = 0

        for content in contents.iterator():
            old_key = str(content.file)
            prefix_path, _, basename = old_key.rpartition("/")

            if not UUID_FILENAME_RE.match(basename):
                continue

            new_basename = basename[33:]  # 32 hex chars + 1 underscore
            if not new_basename:
                self.stderr.write(
                    f"Skipping {old_key}: filename would be empty after removing UUID prefix"  # noqa: E501
                )
                skipped_count += 1
                continue

            new_key = f"{prefix_path}/{new_basename}" if prefix_path else new_basename

            conflicting = (
                WebsiteContent.objects.filter(file=new_key)
                .exclude(pk=content.pk)
                .first()
            )
            if conflicting:
                self.stderr.write(
                    f"Skipping {old_key}: target key {new_key} already used by content pk={conflicting.pk}"  # noqa: E501
                )
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(f"Would rename: {old_key} -> {new_key}")
                renamed_count += 1
                continue

            try:
                s3.copy_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/{old_key}",
                    Key=new_key,
                    ACL="public-read",
                )
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=old_key,
                )
                content.file = new_key
                content.save()
                drive_file = DriveFile.objects.filter(resource=content).first()
                if drive_file and drive_file.s3_key == old_key:
                    drive_file.s3_key = new_key
                    drive_file.save()
                self.stdout.write(f"Renamed: {old_key} -> {new_key}")
                renamed_count += 1
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Error renaming {old_key} to {new_key}: {exc!s}")
                error_count += 1

        if dry_run:
            self.stdout.write(
                f"Dry run complete: {renamed_count} files would be renamed, {skipped_count} skipped"  # noqa: E501
            )
        else:
            self.stdout.write(
                f"Done: {renamed_count} renamed, {skipped_count} skipped, {error_count} errors"  # noqa: E501
            )
