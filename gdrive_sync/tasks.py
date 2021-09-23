"""gdrive_sync tasks"""
import logging
from datetime import datetime

import celery
import pytz
from botocore.exceptions import ClientError
from celery import chain
from dateutil.parser import parse
from django.conf import settings
from django.db import transaction

from gdrive_sync import api
from gdrive_sync.api import get_file_list, get_resource_type, process_file_result
from gdrive_sync.constants import DRIVE_API_FILES, DRIVE_FOLDER_VIDEOS
from gdrive_sync.decorators import is_gdrive_enabled
from gdrive_sync.models import DriveApiQueryTracker, DriveFile
from main.celery import app
from videos.api import create_media_convert_job
from videos.constants import VideoStatus
from videos.models import Video
from websites.models import WebsiteContent


# pylint:disable=unused-argument, raising-format-tuple

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


@app.task(bind=True)
@transaction.atomic
def create_resource_from_gdrive(self, drive_file_id: str):
    """Create a WebsiteContent resource from a Google Drive file for an OCW site"""
    drive_file = DriveFile.objects.get(file_id=drive_file_id)
    resource = drive_file.resource
    if not resource:
        resource = WebsiteContent.objects.create(
            website=drive_file.website,
            title=drive_file.name,
            file=drive_file.s3_key,
            type="resource",
            metadata={"resourcetype": get_resource_type(drive_file.s3_key)},
        )
    else:
        resource.file = drive_file.s3_key
        resource.save()
    drive_file.resource = resource
    drive_file.save()


@app.task(bind=True, name="import_recent_files")
@is_gdrive_enabled
def import_recent_files(self, last_dt: str = None, import_video: bool = False):
    """
    Query the Drive API for recently uploaded or modified files and process them
    if they are in folders that match Website short_ids or names.
    """
    if last_dt and isinstance(last_dt, str):
        # Dates get serialized into strings when passed to celery tasks
        last_dt = parse(last_dt).replace(tzinfo=pytz.UTC)
    file_token_obj, _ = DriveApiQueryTracker.objects.get_or_create(
        api_call=DRIVE_API_FILES, for_video=import_video
    )
    query = (
        f"({'' if import_video else 'not '}mimeType contains 'video/' and not trashed)"
    )
    fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"
    last_checked = last_dt or file_token_obj.last_dt
    if last_checked:
        dt_str = last_checked.strftime("%Y-%m-%dT%H:%M:%S.%f")
        query += f" and (modifiedTime > '{dt_str}' or createdTime > '{dt_str}')"

    gdfiles = get_file_list(query=query, fields=fields)
    chains = []
    for gdfile in gdfiles:
        drive_file = process_file_result(gdfile)
        if drive_file:
            maxLastTime = datetime.strptime(
                max(gdfile.get("createdTime"), gdfile.get("modifiedTime")),
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=pytz.utc)
            if not last_checked or maxLastTime > last_checked:
                last_checked = maxLastTime
            chained_task = (
                transcode_drive_file_video
                if DRIVE_FOLDER_VIDEOS in drive_file.drive_path
                else create_resource_from_gdrive
            )
            chains.append(
                chain(
                    stream_drive_file_to_s3.s(drive_file.file_id),
                    chained_task.si(drive_file.file_id),
                )
            )
    file_token_obj.last_dt = last_checked
    file_token_obj.save()
    raise self.replace(celery.group(*chains))


@app.task(bind=True, name="import_website_files")
@is_gdrive_enabled
def import_website_files(self, short_id: str):
    """Query the Drive API for all children of a website folder (files_final subfolder) and import the files"""
    fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"
    common_query = 'mimeType = "application/vnd.google-apps.folder" and not trashed'
    folders = get_file_list(
        query=f'name = "{short_id}" and {common_query}', fields=fields
    )
    if len(folders) != 1:
        raise Exception(
            "Expected 1 drive folder for %s but found %d", short_id, len(folders)
        )
    query = f'parents = "{folders[0]["id"]}" and name="files_final" and {common_query}'
    files_folder = get_file_list(query=query, fields=fields)
    if len(files_folder) != 1:
        raise Exception(
            "Expected 1 drive folder for %s/files_final but found %d",
            short_id,
            len(files_folder),
        )
    chains = []
    gdfiles = get_file_list(
        query=f'parents = "{files_folder[0]["id"]}" and not {common_query}',
        fields=fields,
    )
    for gdfile in gdfiles:
        drive_file = process_file_result(gdfile)
        if drive_file:
            chains.append(
                chain(
                    stream_drive_file_to_s3.s(drive_file.file_id),
                    create_resource_from_gdrive.si(drive_file.file_id),
                )
            )
    if len(chains) > 0:
        raise self.replace(celery.group(*chains))


@app.task(bind=True)
def import_gdrive_videos(self):
    """Import any new videos uploaded to Google Drive"""
    raise self.replace(import_recent_files.si(import_video=True))


@app.task(bind=True)
def import_gdrive_files(self):
    """Import any new non-video files uploaded to Google Drive"""
    raise self.replace(import_recent_files.si(import_video=False))


@app.task(name="create_gdrive_folders")
@is_gdrive_enabled
def create_gdrive_folders(website_short_id: str):
    """Create gdrive folder for website if it doesn't already exist"""
    api.create_gdrive_folders(website_short_id)
