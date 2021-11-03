""" Constants for gdrive_sync """
from main.constants import STATUS_CREATED


DRIVE_API_CHANGES = "changes"
DRIVE_API_FILES = "files"
DRIVE_API_RESOURCES = [DRIVE_API_FILES, DRIVE_API_CHANGES]

DRIVE_FOLDER_VIDEOS_FINAL = "videos_final"
DRIVE_FOLDER_FILES_FINAL = "files_final"
DRIVE_FOLDER_FILES = "files"
DRIVE_FILE_FIELDS = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"
DRIVE_MIMETYPE_FOLDER = "application/vnd.google-apps.folder"


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
