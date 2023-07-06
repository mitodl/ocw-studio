"""Populate file_size meta field for resources."""
from typing import Optional

import requests
from django.conf import settings
from django.db.models import Q

from content_sync.api import upsert_content_sync_state
from gdrive_sync.models import DriveFile
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_resource
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.models import Website, WebsiteContent


class Command(WebsiteFilterCommand):
    """
    Populate file_size metadata for file resources.

    Usage Examples

    ./manage.py populate_file_sizes
    ./manage.py populate_file_sizes --filter course-id
    ./manage.py populate_file_sizes --filter course-id --verbosity 2 --override-existing
    """

    help = __doc__

    # s3 resource bucket
    __bucket = None

    _verbosity = 1
    _override_existing = False

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--override-existing",
            dest="override_existing",
            action="store_true",
            default=False,
            help="Override existing file_size values",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        self.stdout.write("Populating file sizes...")

        s3 = get_boto3_resource("s3")
        self.__bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        self._verbosity = options["verbosity"]
        self._override_existing = options["override_existing"]

        if self.filter_list:
            website_queryset = Website.objects.filter(
                Q(name__in=self.filter_list) | Q(short_id__in=self.filter_list)
            )
        else:
            website_queryset = Website.objects.all()

        websites = list(website_queryset)
        websites_count = len(websites)

        self.log_verbose(f"Scanning {websites_count} websites.")

        for index, website in enumerate(websites):
            self.stdout.write(f"Progress {index}/{websites_count} completed.")
            self.log_verbose(f"Starting file size population for {website.name}.")

            self._populate_file_sizes(website)

            website.has_unpublished_draft = True
            website.has_unpublished_live = True
            website.save()

        self.stdout.write("Done.")

    @property
    def is_verbose(self):
        """Whether or not verbose logging is enabled."""
        return self._verbosity > 1

    def log_verbose(self, message: str):
        """Utility method to log messages only in verbose mode."""
        if self.is_verbose:
            self.stdout.write(message)

    def _populate_file_sizes(self, website: Website):
        """Populate file sizes for resources present in `website`."""
        updated_drive_files = []
        updated_contents = []

        for content in website.websitecontent_set.filter(type=CONTENT_TYPE_RESOURCE):
            if not self._override_existing and content.metadata.get("file_size"):
                continue

            self._populate_file_size_metadata(content)
            drive_files = content.drivefile_set.all()
            for drive_file in drive_files:
                self._populate_drive_file_size(drive_file)

            updated_drive_files.extend(drive_files)
            updated_contents.append(content)

        DriveFile.objects.bulk_update(updated_drive_files, ["size"])
        WebsiteContent.objects.bulk_update(updated_contents, ["metadata"])

        # bulk_update does not call pre/post_save signals.
        # So we'll do the sync state update ourselves.
        for content in updated_contents:
            upsert_content_sync_state(content)

    def _populate_file_size_metadata(self, content: WebsiteContent):
        """Populate `content.metadata.file_size` with an appropriate value."""
        # Our data has different fields used for file location throughout the years.
        # We check them in order of "recently adopted."
        file_key = (
            content.file.name
            or content.metadata.get("file")
            or content.metadata.get("file_location")
        )

        if file_key:
            content.metadata["file_size"] = self._get_s3_file_size(file_key)
        elif content.metadata.get("video_files", {}).get("archive_url"):
            # Some of our video resources are directly linked to YT videos, and their
            # downloadable content is in an archive url.
            file_url = content.metadata["video_files"]["archive_url"]
            content.metadata["file_size"] = self._get_url_content_length(file_url)
        else:
            self.stdout.write(f"WebsiteContent {content} has no file associated to it.")
            content.metadata["file_size"] = None

        self.log_verbose(
            f"WebsiteContent {content} now has file_size {content.metadata['file_size']}."
        )

    def _populate_drive_file_size(self, drive_file: DriveFile):
        """Populate `drive_file.size` with an appropriate value."""
        file_key = drive_file.s3_key

        if file_key:
            drive_file.size = self._get_s3_file_size(file_key)
        else:
            self.stderr.write(f"DriveFile {drive_file} has no file associated to it.")

        self.log_verbose(f"DriveFile {drive_file} now has size {drive_file.size}.")

    def _get_s3_file_size(self, file_key: str) -> Optional[int]:
        """Query s3 to get the size of `file_key`."""
        if file_key and self.__bucket:
            try:
                return self.__bucket.Object(file_key).content_length
            except Exception as ex:  # pylint:disable=broad-except
                self.stderr.write(f"Could not read size for key {file_key}. {ex}")

    def _get_url_content_length(self, file_url: str) -> Optional[int]:
        """Make a HTTP request to get the file size for `file_url`."""
        try:
            response = requests.request("HEAD", file_url, headers={}, data={})
            return response.headers.get("Content-Length")
        except Exception as ex:  # pylint:disable=broad-except
            self.stderr.write(f"Could not read size for url {file_url}. {ex}")
