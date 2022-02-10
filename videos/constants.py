""" constants for videos """
from main.constants import STATUS_COMPLETE, STATUS_CREATED, STATUS_FAILED


DESTINATION_YOUTUBE = "youtube"
DESTINATION_ARCHIVE = "archive"

ALL_DESTINATIONS = [DESTINATION_YOUTUBE, DESTINATION_ARCHIVE]

YT_THUMBNAIL_IMG = "https://img.youtube.com/vi/{video_id}/default.jpg"


class VideoStatus:
    """Simple class for possible VideoFile statuses"""

    CREATED = STATUS_CREATED
    TRANSCODING = "Transcoding"
    SUBMITTED_FOR_TRANSCRIPTION = "submitted_for_transcription"
    FAILED = STATUS_FAILED
    COMPLETE = STATUS_COMPLETE

    ALL_STATUSES = [CREATED, TRANSCODING, SUBMITTED_FOR_TRANSCRIPTION, FAILED, COMPLETE]


class VideoJobStatus:
    """Simple class for possible VideoJob statuses"""

    CREATED = STATUS_CREATED
    FAILED = STATUS_FAILED
    COMPLETE = STATUS_COMPLETE


class VideoFileStatus:
    """Simple class for possible VideoFile statuses"""

    CREATED = STATUS_CREATED
    UPLOADED = "Uploaded"
    FAILED = STATUS_FAILED
    COMPLETE = STATUS_COMPLETE


class YouTubeStatus:
    """Simple class for YouTube statuses"""

    UPLOADED = "uploaded"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PROCESSED = "processed"
    REJECTED = "rejected"
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    RETRY = "retry"
