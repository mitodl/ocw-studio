"""
Management command to backfill Google Drive folder content
from website's S3 bucket.
"""
import io

from botocore.exceptions import BotoCoreError
from django.db.models import Q
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from mitol.common.utils import now_in_utc

from gdrive_sync.api import (
    get_drive_service,
    query_files,
    walk_gdrive_folder,
)
from gdrive_sync.constants import (
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    DriveFileStatus,
)
from gdrive_sync.models import DriveFile
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

    def handle(self, *args, **options):
        """
        Handle the backfilling of Google Drive folder with content from S3.
        """

        super().handle(*args, **options)
        s3 = get_boto3_client("s3")
        gdrive_service = get_drive_service()
        websites = Website.objects.all()
        website_filter = options["filter"].lower()
        if options["filter"]:
            websites = websites.filter(
                Q(name__startswith=website_filter)
                | Q(short_id__startswith=website_filter)
            )
        if not websites:
            self.stdout.write("No websites found.")
            return
        for website in websites:
            self.stdout.write(f"Processing website: {website.name}")
            gdrive_folder = website.gdrive_folder
            gdrive_query = (
                f'parents = "{gdrive_folder}" and '
                f'name="{DRIVE_FOLDER_FILES_FINAL}" and '
                f'mimeType = "{DRIVE_MIMETYPE_FOLDER}" and not trashed'
            )
            subfolder_list = list(
                query_files(query=gdrive_query, fields=DRIVE_FILE_FIELDS)
            )
            gdrive_files = list(
                walk_gdrive_folder(subfolder_list[0]["id"], fields=DRIVE_FILE_FIELDS)
            )
            if len(gdrive_files) > 0:
                self.stdout.write(
                    f"The Google Drive folder {gdrive_folder} already has "
                    f"content. Skipping backfill."
                )
                return
            resources = (
                WebsiteContent.objects.filter(website=website)
                .filter(type=CONTENT_TYPE_RESOURCE)
                .exclude(metadata__resourcetype=RESOURCE_TYPE_VIDEO)
            )
            for resource in resources:
                file_obj = io.BytesIO()
                self.stdout.write(
                    f"Downloading file {resource.file!s} from S3 bucket "
                    f"{settings.AWS_STORAGE_BUCKET_NAME}."
                )
                try:
                    s3.download_fileobj(
                        settings.AWS_STORAGE_BUCKET_NAME, str(resource.file), file_obj
                    )
                except BotoCoreError as e:
                    self.stdout.write(f"Error downloading {resource.file!s}: {e!s}")
                    continue

                file_obj.seek(0)
                media = MediaIoBaseUpload(
                    file_obj,
                    mimetype=resource.metadata["file_type"],
                    resumable=True,
                )
                if resource.title:
                    name = resource.title
                elif resource.metadata.get("title"):
                    name = resource.metadata["title"]
                else:
                    name = str(resource.file)
                file_metadata = {
                    "name": name,
                    "mimeType": resource.metadata["file_type"],
                    "parents": [subfolder_list[0]["id"]],
                }
                try:
                    gdrive_file = (
                        gdrive_service.files()
                        .create(
                            body=file_metadata,
                            media_body=media,
                            fields="id",
                            supportsAllDrives=True,
                        )
                        .execute()
                    )
                except HttpError as e:
                    self.stdout.write(
                        f"Error uploading file {resource.file!s}"
                        f" to Google Drive: {e!s}"
                    )
                    continue
                gdrive_dl = (
                    gdrive_service.files()
                    .get(
                        fileId=gdrive_file.get("id"),
                        fields="id, md5Checksum, createdTime,"
                        "modifiedTime, size, webContentLink",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                DriveFile.objects.create(
                    file_id=gdrive_file.get("id"),
                    checksum=gdrive_dl.get("md5Checksum"),
                    name=name,
                    mime_type=resource.metadata["file_type"],
                    status=DriveFileStatus.COMPLETE,
                    website=website,
                    s3_key=str(resource.file).lstrip("/"),
                    resource=resource,
                    drive_path=f"{website.short_id}/{DRIVE_FOLDER_FILES_FINAL}",
                    modified_time=gdrive_dl.get("modifiedTime"),
                    created_time=gdrive_dl.get("createdTime"),
                    size=gdrive_dl.get("size"),
                    download_link=gdrive_dl.get("webContentLink"),
                    sync_dt=now_in_utc(),
                )
                self.stdout.write(f"{resource.file!s} uploaded to Google Drive folder.")
            self.stdout.write(f"Completed processing website: {website.name}\n\n")
