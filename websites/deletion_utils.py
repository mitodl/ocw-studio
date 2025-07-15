from pathlib import Path

from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from gdrive_sync.api import delete_drive_file, get_drive_service
from gdrive_sync.models import DriveFile
from videos.tasks import delete_s3_objects
from websites.models import WebsiteContent


def delete_resource(content: WebsiteContent):
    """
    Delete a resouce: WebsiteContent object, driveFile, S3 object,
    and file itself from gdrive.
    """
    drive_file = DriveFile.objects.filter(resource=content).first()
    if drive_file_id := drive_file and drive_file.file_id:
        delete_drive_file(drive_file, sync_datetime=now_in_utc())
        ds = get_drive_service()
        ds.files().delete(fileId=drive_file_id, supportsAllDrives=True).execute()
        if content.file:
            delete_s3_objects.delay(key=drive_file.s3_key)
    content.delete()


def delete_related_captions_and_transcript(content: WebsiteContent):
    """
    Delete related captions and transcript file for a video.
    """
    video_files = content.metadata.get("video_files", {})
    for attr in ("video_captions_file", "video_transcript_file"):
        key = video_files.get(attr)
        if not key:
            continue
        base_name = Path(key).stem
        qs = WebsiteContent.objects.filter(website=content.website)
        related = qs.filter(
            Q(file=key) | Q(file=key.strip("/")) | Q(filename=base_name)
        ).first()
        if related:
            # if captions or transcript file is found, delete it
            delete_resource(related)
