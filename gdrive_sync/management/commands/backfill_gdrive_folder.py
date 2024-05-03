"""
Management command to backfill Google Drive folder content
from website's S3 bucket.
"""
import io

from botocore.exceptions import BotoCoreError
from django.db.models import Q
from django.db.models.signals import pre_delete
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from httplib2 import Response
from mitol.common.utils import now_in_utc

from gdrive_sync.api import get_drive_service, query_files, walk_gdrive_folder
from gdrive_sync.constants import (
    DRIVE_FILE_CREATED_TIME,
    DRIVE_FILE_DOWNLOAD_LINK,
    DRIVE_FILE_FIELDS,
    DRIVE_FILE_ID,
    DRIVE_FILE_MD5_CHECKSUM,
    DRIVE_FILE_MODIFIED_TIME,
    DRIVE_FILE_SIZE,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    DriveFileStatus,
)
from gdrive_sync.models import DriveFile
from gdrive_sync.signals import delete_from_s3
from gdrive_sync.utils import get_gdrive_file, get_resource_name
from main import settings
from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_client
from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.models import Website, WebsiteContent


class Command(WebsiteFilterCommand):
    """Populate Google Drive folder content from website's S3 bucket."""

    def add_arguments(self, parser):
        """Add arguments to the command's argument parser."""
        super().add_arguments(parser)
        filter_action = next(
            action
            for action in parser._actions  # noqa: SLF001
            if action.dest == "filter"
        )
        filter_action.required = True
        filter_action.help = "String to filter websites by name or short ID."

    def handle(self, *args, **options):
        """
        Handle the backfilling of Google Drive folder with content from S3.
        """

        super().handle(*args, **options)
        self.s3 = get_boto3_client("s3")
        self.gdrive_service = get_drive_service()
        websites = self.get_websites(options["filter"].lower())
        if not websites:
            self.stdout.write("No websites found.")
            return
        for website in websites:
            self.process_website(website)

    def get_websites(self, website_filter):
        """
        Retrieve a list of websites based on the given filter.

        Args:
            website_filter (str): A string to filter the websites by name or short ID.

        Returns:
            QuerySet: A queryset containing the filtered websites.
        """
        websites = Website.objects.all()
        return websites.filter(
            Q(name__startswith=website_filter) | Q(short_id__startswith=website_filter)
        )

    def process_website(self, website):
        """
        Process the given website by checking if the corresponding Google Drive folder
        is empty. If it is empty, it backfills the folder with resources from S3.

        Args:
            website (Website): The website object to be processed.
        """
        self.stdout.write(f"Processing website: {website.name}")
        gdrive_folder = website.gdrive_folder
        gdrive_query = self.get_gdrive_query(gdrive_folder)
        subfolder_list = list(query_files(query=gdrive_query, fields=DRIVE_FILE_FIELDS))
        list(walk_gdrive_folder(subfolder_list[0]["id"], fields=DRIVE_FILE_FIELDS))
        resources = self.get_resources(website)
        for resource in resources:
            self.process_resource(resource, website, subfolder_list[0]["id"])

    def get_gdrive_query(self, gdrive_folder):
        """
        Return the Google Drive query string for retrieving files within a given folder.

        Args:
            gdrive_folder (str): The ID of the Google Drive folder.

        Returns:
            str: The Google Drive query string.
        """
        return (
            f'parents = "{gdrive_folder}" and '
            f'name="{DRIVE_FOLDER_FILES_FINAL}" and '
            f'mimeType = "{DRIVE_MIMETYPE_FOLDER}" and not trashed'
        )

    def get_resources(self, website):
        """
        Retrieve a queryset of non-video resources for a given website.

        Args:
            website (Website): The website for which to retrieve the resources.

        Returns:
            QuerySet: A queryset of non-video resources.
        """
        return (
            WebsiteContent.objects.filter(website=website)
            .filter(type=CONTENT_TYPE_RESOURCE)
            .exclude(metadata__resourcetype=RESOURCE_TYPE_VIDEO)
        )

    def process_resource(self, resource, website, parent_id):
        """
        Process a resource by downloading it from S3, uploading it to Google Drive,
        and creating a DriveFile object in the Django database.

        Args:
            resource (WebsiteContent): The resource to be processed.
            website (Website): The website associated with the resource.
            parent_id (str): The ID of the parent folder in Google Drive.

        """
        drive_file = DriveFile.objects.filter(resource=resource).first()
        if drive_file:
            try:
                gdrive_resp = (
                    self.gdrive_service.files()
                    .get(
                        fileId=drive_file.file_id,
                        supportsAllDrives=True,
                        fields="trashed",
                    )
                    .execute()
                )
                if gdrive_resp["trashed"]:
                    self.raise_http_error()

            except HttpError as error:
                if error.resp.status == 404:  # noqa: PLR2004
                    self.stdout.write(
                        "No file found at {} for resource {}. "
                        "Deleting DriveFile and continuing.".format(
                            drive_file.download_link, resource.file
                        )
                    )
                    self.delete_drivefile_keep_s3(drive_file)
                else:
                    self.stdout.write(
                        "Unexpected error when checking {} for resource {}. "
                        "Skipping.".format(drive_file.download_link, resource.file)
                    )
                    return
            else:
                self.stdout.write(
                    "File exists at {} for resource {}. Skipping.".format(
                        drive_file.download_link, resource.file
                    )
                )
                return
        file_obj = io.BytesIO()
        self.stdout.write(
            f"Downloading file {resource.file} from S3 bucket "
            f"{settings.AWS_STORAGE_BUCKET_NAME}."
        )
        try:
            self.s3.download_fileobj(
                settings.AWS_STORAGE_BUCKET_NAME,
                f"{resource.file}".lstrip("/"),
                file_obj,
            )

        except BotoCoreError as e:
            self.stdout.write(f"Error downloading {resource.file}: {e}")
            return

        file_obj.seek(0)
        media = MediaIoBaseUpload(
            file_obj,
            mimetype=resource.metadata["file_type"],
            resumable=True,
        )
        name = get_resource_name(resource)
        file_metadata = {
            "name": name,
            "mimeType": resource.metadata["file_type"],
            "parents": [parent_id],
        }
        try:
            gdrive_file = self.upload_file_to_gdrive(file_metadata, media)
        except HttpError as e:
            self.stdout.write(
                f"Error uploading file {resource.file} to Google Drive: {e}"
            )
            return

        gdrive_dl = get_gdrive_file(self.gdrive_service, gdrive_file.get(DRIVE_FILE_ID))
        DriveFile.objects.create(
            file_id=gdrive_file.get(DRIVE_FILE_ID),
            checksum=gdrive_dl.get(DRIVE_FILE_MD5_CHECKSUM),
            name=name,
            mime_type=resource.metadata["file_type"],
            status=DriveFileStatus.COMPLETE,
            website=website,
            s3_key=str(resource.file).lstrip("/"),
            resource=resource,
            drive_path=f"{website.short_id}/{DRIVE_FOLDER_FILES_FINAL}",
            modified_time=gdrive_dl.get(DRIVE_FILE_MODIFIED_TIME),
            created_time=gdrive_dl.get(DRIVE_FILE_CREATED_TIME),
            size=gdrive_dl.get(DRIVE_FILE_SIZE),
            download_link=gdrive_dl.get(DRIVE_FILE_DOWNLOAD_LINK),
            sync_dt=now_in_utc(),
        )
        self.stdout.write(f"{resource.file} uploaded to Google Drive folder.")

    def upload_file_to_gdrive(self, file_metadata, media):
        """Upload a file to Google Drive."""
        return (
            self.gdrive_service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields=DRIVE_FILE_ID,
                supportsAllDrives=True,
            )
            .execute()
        )

    def delete_drivefile_keep_s3(self, drive_file):
        """Delete a DriveFile object without deleting the corresponding file from S3."""
        pre_delete.disconnect(delete_from_s3, sender=DriveFile)
        drive_file.delete()
        pre_delete.connect(delete_from_s3, sender=DriveFile)

    def raise_http_error(self):
        """
        Raise an HttpError with a 404 status code.
        """
        resp = Response({"status": 404, "reason": "File not found"})
        content = b"File not found"
        raise HttpError(resp, content)
