"""Common utilities"""

from typing import Optional

import requests

from gdrive_sync.constants import (
    DRIVE_FILE_CREATED_TIME,
    DRIVE_FILE_DOWNLOAD_LINK,
    DRIVE_FILE_ID,
    DRIVE_FILE_MD5_CHECKSUM,
    DRIVE_FILE_MODIFIED_TIME,
    DRIVE_FILE_SIZE,
)
from gdrive_sync.models import DriveFile
from websites.models import WebsiteContent


def fetch_content_file_size(
    content: WebsiteContent, bucket: "s3.Bucket"  # noqa: F821
) -> Optional[int]:
    """Return the size (in bytes) of the file associated with `content`."""
    size = None

    # Our data has different fields used for file location throughout the years.
    # We check them in order of "recently adopted."
    file_key = (
        content.file.name
        or content.metadata.get("file")
        or content.metadata.get("file_location")
    )

    if file_key:
        file_key = file_key.strip("/")
        size = bucket.Object(file_key).content_length
    elif content.metadata.get("video_files", {}).get("archive_url"):
        # Some of our video resources are directly linked to YT videos, and their
        # downloadable content is in an archive url.
        file_url = content.metadata["video_files"]["archive_url"]
        response = requests.request("HEAD", file_url, headers={}, data={}, timeout=30)
        size = response.headers.get("Content-Length")

    return size


def fetch_drive_file_size(
    drive_file: DriveFile, bucket: "s3.Bucket"  # noqa: F821
) -> Optional[int]:  # noqa: F821, RUF100
    """Return the size (in bytes) of the file associated with `drive_file.s3_key`."""
    size = None
    file_key = drive_file.s3_key

    if file_key:
        size = bucket.Object(file_key).content_length

    return size


def get_gdrive_file(gdrive_service, file_id):
    """
    Retrieve information about a Google Drive file.

    Args:
        file_id (str): The ID of the file to retrieve.

    Returns:
        dict: A dictionary containing information about the file.
    """
    return (
        gdrive_service.files()
        .get(
            fileId=file_id,
            fields=(
                f"{DRIVE_FILE_ID},{DRIVE_FILE_MD5_CHECKSUM},"
                f"{DRIVE_FILE_CREATED_TIME},{DRIVE_FILE_MODIFIED_TIME},"
                f"{DRIVE_FILE_SIZE},{DRIVE_FILE_DOWNLOAD_LINK}"
            ),
            supportsAllDrives=True,
        )
        .execute()
    )


def get_resource_name(resource):
    """
    Infer the name of the resource based on the title or filename.

    Args:
        resource (WebsiteContent): The resource object.

    Returns:
        The name of the resource.
    """
    if resource.title:
        return resource.title
    elif resource.metadata.get("title"):
        return resource.metadata["title"]
    else:
        return str(resource.file)
