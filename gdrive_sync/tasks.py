"""gdrive_sync tasks"""
import logging
from datetime import datetime

import celery
import pytz
from celery import chain, chord
from dateutil.parser import parse
from django.conf import settings

from content_sync.tasks import sync_website_content
from gdrive_sync import api
from gdrive_sync.api import (
    create_gdrive_resource_content,
    is_gdrive_enabled,
    process_file_result,
    query_files,
    transcode_gdrive_video,
    walk_gdrive_folder,
)
from gdrive_sync.constants import (
    DRIVE_API_FILES,
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
)
from gdrive_sync.models import DriveApiQueryTracker, DriveFile
from main.celery import app
from main.tasks import chord_finisher
from websites.models import Website


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
    transcode_gdrive_video(DriveFile.objects.get(file_id=drive_file_id))


@app.task(bind=True)
def create_resource_from_gdrive(self, drive_file_id: str):
    """Create a WebsiteContent resource from a Google Drive file for an OCW site"""
    create_gdrive_resource_content(DriveFile.objects.get(file_id=drive_file_id))


@app.task(bind=True)
def import_recent_files(self, last_dt: str = None):  # pylint: disable=too-many-locals
    """
    Query the Drive API for recently uploaded or modified files and process them
    if they are in folders that match Website short_ids or names.
    """
    if not is_gdrive_enabled():
        return
    if last_dt and isinstance(last_dt, str):
        # Dates get serialized into strings when passed to celery tasks
        last_dt = parse(last_dt).replace(tzinfo=pytz.UTC)
    file_token_obj, _ = DriveApiQueryTracker.objects.get_or_create(
        api_call=DRIVE_API_FILES
    )
    query = "(not trashed and not mimeType = 'application/vnd.google-apps.folder')"
    last_checked = last_dt or file_token_obj.last_dt
    if last_checked:
        dt_str = last_checked.strftime("%Y-%m-%dT%H:%M:%S.%f")
        query += f" and (modifiedTime > '{dt_str}' or createdTime > '{dt_str}')"

    chains = []
    website_names = set()
    for gdfile in query_files(query=query, fields=DRIVE_FILE_FIELDS):
        drive_file = process_file_result(gdfile)
        if drive_file:
            maxLastTime = datetime.strptime(
                max(gdfile.get("createdTime"), gdfile.get("modifiedTime")),
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=pytz.utc)
            if not last_checked or maxLastTime > last_checked:
                last_checked = maxLastTime
            task_list = [
                stream_drive_file_to_s3.s(drive_file.file_id),
                transcode_drive_file_video.si(drive_file.file_id)
                if drive_file.is_video()
                else None,
                create_resource_from_gdrive.si(drive_file.file_id),
            ]
            chains.append(chain(*[task for task in task_list if task]))
            website_names.add(drive_file.website.name)

    file_token_obj.last_dt = last_checked
    file_token_obj.save()

    if chains:
        # Import the files first, then sync the websites for those files in git
        file_steps = chord(celery.group(*chains), chord_finisher.si())
        website_steps = [
            sync_website_content.si(website_name) for website_name in website_names
        ]
        workflow = chain(file_steps, celery.group(website_steps))
        raise self.replace(celery.group(workflow))


@app.task(bind=True)
def import_website_files(self, short_id: str):
    """Query the Drive API for all children of a website folder and import the files"""
    if not is_gdrive_enabled():
        return
    common_query = f'mimeType = "{DRIVE_MIMETYPE_FOLDER}" and not trashed'
    site_folders = list(
        query_files(
            query=f'name = "{short_id}" and {common_query}', fields=DRIVE_FILE_FIELDS
        )
    )
    if len(site_folders) != 1:
        raise Exception(
            "Expected 1 drive folder for %s but found %d", short_id, len(site_folders)
        )

    chains = []
    for subfolder in [DRIVE_FOLDER_FILES_FINAL, DRIVE_FOLDER_VIDEOS_FINAL]:
        query = f'parents = "{site_folders[0]["id"]}" and name="{subfolder}" and {common_query}'
        subfolder_list = list(query_files(query=query, fields=DRIVE_FILE_FIELDS))
        if len(subfolder_list) != 1:
            log.error(
                "Expected 1 drive folder for %s/%s but found %d",
                short_id,
                subfolder,
                len(subfolder_list),
            )
            continue
        gdfiles = walk_gdrive_folder(
            subfolder_list[0]["id"],
            DRIVE_FILE_FIELDS,
        )
        for gdfile in gdfiles:
            drive_file = process_file_result(gdfile)
            if drive_file:
                task_list = [
                    stream_drive_file_to_s3.s(drive_file.file_id),
                    transcode_drive_file_video.si(drive_file.file_id)
                    if drive_file.is_video()
                    else None,
                    create_resource_from_gdrive.si(drive_file.file_id),
                ]
                chains.append(chain(*[task for task in task_list if task]))
    if chains:
        # Import the files first, then sync the website for those files in git
        file_steps = chord(celery.group(*chains), chord_finisher.si())
        website_step = sync_website_content.si(
            Website.objects.get(short_id=short_id).name
        )
        workflow = chain(file_steps, website_step)
        raise self.replace(celery.group(workflow))


@app.task()
def create_gdrive_folders(website_short_id: str):
    """Create gdrive folder for website if it doesn't already exist"""
    if is_gdrive_enabled():
        api.create_gdrive_folders(website_short_id)
