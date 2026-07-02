import logging

from mitol.common.utils.datetime import now_in_utc

from content_sync.decorators import retry_on_failure
from gdrive_sync.api import delete_drive_file, get_drive_service
from gdrive_sync.models import DriveFile
from videos.tasks import delete_s3_objects
from websites.models import WebsiteContent

log = logging.getLogger(__name__)


@retry_on_failure
def delete_drive_file_from_gdrive(file_id: str):
    """
    Delete a file from Google Drive using drive_file.file_id.
    """
    log.info("Deleting Google Drive file %s", file_id)
    try:
        ds = get_drive_service()
        ds.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        log.info("Successfully deleted Google Drive file %s", file_id)
    except Exception:
        log.exception("Failed to delete Google Drive file %s", file_id)
        raise


def delete_resource(content: WebsiteContent):
    """
    Delete a resource: WebsiteContent object, driveFile, S3 object,
    and file itself from gdrive.
    """
    drive_file = DriveFile.objects.filter(resource=content).first()
    if drive_file:
        if drive_file.file_id:
            delete_drive_file_from_gdrive(drive_file.file_id)
            if content.file:
                delete_s3_objects.delay(key=drive_file.s3_key)
        delete_drive_file(drive_file, sync_datetime=now_in_utc())
    content.delete()


def delete_related_captions_and_transcript(content: WebsiteContent):
    """Delete related captions and transcript resources for a video."""
    video_files = content.metadata.get("video_files", {})
    for resource_field in ("video_captions_resources", "video_transcript_resources"):
        relation = video_files.get(resource_field)
        if not isinstance(relation, dict):
            continue
        content_val = relation.get("content")
        if isinstance(content_val, str):
            text_ids = [content_val] if content_val else []
        elif isinstance(content_val, list):
            text_ids = [t for t in content_val if t]
        else:
            text_ids = []
        for text_id in text_ids:
            related = WebsiteContent.objects.filter(
                website=content.website, text_id=text_id
            ).first()
            if related:
                delete_resource(related)
