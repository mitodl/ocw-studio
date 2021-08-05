""" Constants for gdrive_sync """

DRIVE_API_CHANGES = "changes"
DRIVE_API_FILES = "files"
DRIVE_API_RESOURCES = [DRIVE_API_FILES, DRIVE_API_CHANGES]


class DriveFileStatus:
    """Simple class for possible DriveFile statuses"""

    CREATED = "Created"
    UPLOADING = "Uploading"
    UPLOAD_FAILED = "Upload failed"
    UPLOAD_COMPLETE = "Upload Complete"

    ALL_STATUSES = [CREATED, UPLOADING, UPLOAD_FAILED, UPLOAD_COMPLETE]
