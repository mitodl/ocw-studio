"""gdrive_sync tasks"""
from django.conf import settings

from gdrive_sync import api
from gdrive_sync.models import DriveFile
from main.celery import app


@app.task
def stream_drive_file_to_s3(drive_file_id: int):
    """ Stream a Google Drive file to S3 """
    if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
        drive_file = DriveFile.objects.get(file_id=drive_file_id)
        api.stream_to_s3(drive_file)


@app.task
def import_gdrive_videos():
    """Import any new videos uploaded to Google Drive"""
    if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
        api.import_recent_videos()
