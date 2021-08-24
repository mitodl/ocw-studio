"""gdrive_sync tasks"""
import logging

from botocore.exceptions import ClientError
from django.conf import settings

from gdrive_sync import api
from gdrive_sync.models import DriveFile
from main.celery import app
from videos.api import create_media_convert_job
from videos.constants import VideoStatus
from videos.models import Video


# pylint:disable=unused-argument

log = logging.getLogger(__name__)


@app.task(bind=True)
def stream_drive_file_to_s3(self, drive_file_id: str):
    """ Stream a Google Drive file to S3 """
    if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
        drive_file = DriveFile.objects.get(file_id=drive_file_id)
        api.stream_to_s3(drive_file)


@app.task(bind=True)
def transcode_drive_file_video(self, drive_file_id: str):
    """Create a MediaConvert transcode job and Video object for the given drive file id"""
    if settings.AWS_ACCOUNT_ID and settings.AWS_REGION and settings.AWS_ROLE_NAME:
        drive_file = DriveFile.objects.get(file_id=drive_file_id)
        video, _ = Video.objects.get_or_create(
            source_key=drive_file.s3_key,
            website=drive_file.website,
            defaults={"status": VideoStatus.CREATED},
        )
        drive_file.video = video
        drive_file.save()
        try:
            create_media_convert_job(video)
        except ClientError:
            log.exception("Error creating transcode job for %s", video.source_key)
            video.state = VideoStatus.FAILED
            video.save()


@app.task
def import_gdrive_videos():
    """Import any new videos uploaded to Google Drive"""
    if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
        api.import_recent_videos()


@app.task
def create_gdrive_folder_if_not_exists(website_short_id: str, website_name: str):
    """Create gdrive folder for website if it doesn't already exist"""
    if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
        api.create_gdrive_folder_if_not_exists(website_short_id, website_name)
