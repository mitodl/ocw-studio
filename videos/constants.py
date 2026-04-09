"""constants for videos"""

from main.constants import STATUS_COMPLETE, STATUS_CREATED, STATUS_FAILED

DESTINATION_YOUTUBE = "youtube"
DESTINATION_ARCHIVE = "archive"

ALL_DESTINATIONS = [DESTINATION_YOUTUBE, DESTINATION_ARCHIVE]

YT_THUMBNAIL_IMG = "https://img.youtube.com/vi/{video_id}/default.jpg"
YT_MAX_LENGTH_TITLE = 100
YT_MAX_LENGTH_DESCRIPTION = 5000

PDF_FORMAT_ID = 46
WEBVTT_FORMAT_ID = 51

# YouTube Data API v3 quota costs and batch size
QUOTA_COST_VIDEO_LIST = 1  # videos.list costs 1 unit per call (up to 50 IDs)
QUOTA_COST_VIDEO_UPDATE = 50  # videos.update costs 50 units
YT_LIST_BATCH_SIZE = 50  # Maximum video IDs per videos.list call

ARCHIVE_URL_FILESIZE_TASK_RATE_LIMIT = "0.1/s"
S3_FILESIZE_TASK_RATE_LIMIT = "5/s"


class VideoStatus:
    """Simple class for possible Video statuses"""

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
    RETRY = "retry"
