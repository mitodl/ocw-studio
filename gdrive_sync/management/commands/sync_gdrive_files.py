"""Sync GDrive files with DB resources."""

import logging

from content_sync.api import get_sync_backend
from gdrive_sync.api import process_file_result
from gdrive_sync.constants import DriveFileStatus
from gdrive_sync.models import DriveFile
from gdrive_sync.tasks import _get_gdrive_files, process_drive_file
from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website

log = logging.getLogger(__name__)


class Command(WebsiteFilterCommand):
    """
    Sync GDrive files with DB resources.

    Usage Examples

    ./manage.py sync_gdrive_files
    ./manage.py sync_gdrive_files --filter course-id
    ./manage.py sync_gdrive_files --filter course-id --filename filename1
    """

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--filename",
            dest="filename",
            default="",
            help="If specified, only trigger processing files whose names are in this comma-delimited list",  # noqa: E501
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        filenames = options["filename"]

        if filenames:
            filenames = [
                filename.strip() for filename in filenames.split(",") if filename
            ]

        website_queryset = self.filter_websites(websites=Website.objects.all())

        for website in website_queryset:
            gdrive_subfolder_files, _ = _get_gdrive_files(website)

            for gdrive_files in gdrive_subfolder_files.values():
                for gdrive_file in gdrive_files:
                    if filenames and gdrive_file["name"] not in filenames:
                        continue

                    try:
                        # Add/Update Drivefile objects and perform necessary operations
                        process_file_result(gdrive_file, website)

                        # Upload to S3 and transcoding operations if video
                        process_drive_file.apply((gdrive_file["id"],))

                        # Get the related drive file and update status
                        drive_file = DriveFile.objects.get(file_id=gdrive_file["id"])
                        drive_file.status = DriveFileStatus.COMPLETE
                        drive_file.save()

                    except:  # pylint:disable=bare-except  # noqa: E722
                        log.exception(
                            "Error processing GDrive file %s for %s",
                            gdrive_file["name"],
                            website.short_id,
                        )

            backend = get_sync_backend(website)
            backend.sync_all_content_to_backend()

        self.stdout.write("Done")
