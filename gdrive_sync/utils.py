"""Common utilities"""
from typing import Optional

import requests

from gdrive_sync.models import DriveFile
from websites.models import WebsiteContent


def fetch_content_file_size(
    content: WebsiteContent, bucket: "s3.Bucket"
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


def fetch_drive_file_size(drive_file: DriveFile, bucket: "s3.Bucket") -> Optional[int]:
    """Return the size (in bytes) of the file associated with `drive_file.s3_key`."""
    size = None
    file_key = drive_file.s3_key

    if file_key:
        size = bucket.Object(file_key).content_length

    return size
