"""Constants for gdrive_sync"""
from main.constants import STATUS_CREATED

DRIVE_API_CHANGES = "changes"
DRIVE_API_FILES = "files"
DRIVE_API_RESOURCES = [DRIVE_API_FILES, DRIVE_API_CHANGES]

DRIVE_FOLDER_VIDEOS_FINAL = "videos_final"
DRIVE_FOLDER_FILES_FINAL = "files_final"
DRIVE_FOLDER_FILES = "files"
DRIVE_FILE_FIELDS = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, size, webContentLink, trashed, parents)"  # noqa: E501
DRIVE_MIMETYPE_FOLDER = "application/vnd.google-apps.folder"

DRIVE_FILE_ID = "id"
DRIVE_FILE_NAME = "name"
DRIVE_FILE_MIME_TYPE = "mimeType"
DRIVE_FILE_MD5_CHECKSUM = "md5Checksum"
DRIVE_FILE_MODIFIED_TIME = "modifiedTime"
DRIVE_FILE_CREATED_TIME = "createdTime"
DRIVE_FILE_SIZE = "size"
DRIVE_FILE_DOWNLOAD_LINK = "webContentLink"

VALID_TEXT_FILE_TYPES = [
    ".pdf",
    ".htm",
    ".html",
    ".txt",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".xml",
    ".json",
    ".rtf",
    ".ps",
    ".odt",
    ".epub",
    ".mobi",
]


class DriveFileStatus:
    """Simple class for possible DriveFile statuses"""

    CREATED = STATUS_CREATED
    UPLOADING = "Uploading"
    UPLOAD_FAILED = "Upload Failed"
    UPLOAD_COMPLETE = "Upload Complete"
    TRANSCODING = "Transcoding"
    TRANSCODE_FAILED = "Transcode Failed"
    COMPLETE = "Complete"
    FAILED = "Failed"
    ALL_STATUSES = [
        CREATED,
        UPLOADING,
        UPLOAD_FAILED,
        UPLOAD_COMPLETE,
        TRANSCODING,
        TRANSCODE_FAILED,
        COMPLETE,
        FAILED,
    ]


class WebsiteSyncStatus:
    """Simple class for possible Website sync statuses"""

    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETE = "Complete"
    FAILED = "Failed"
    ERRORS = "Errors"
