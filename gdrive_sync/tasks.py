"""gdrive_sync tasks"""
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple

import celery
import pytz
from celery import chain, chord
from dateutil.parser import parse
from django.conf import settings
from mitol.common.utils import chunks, now_in_utc

from content_sync.decorators import single_task
from content_sync.tasks import sync_website_content
from gdrive_sync import api
from gdrive_sync.constants import (
    DRIVE_API_FILES,
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    WebsiteSyncStatus,
)
from gdrive_sync.models import DriveApiQueryTracker, DriveFile
from main.celery import app
from main.tasks import chord_finisher
from websites.models import Website


# pylint:disable=unused-argument, raising-format-tuple


log = logging.getLogger(__name__)


@app.task()
def process_drive_file(drive_file_id: str):
    """Run the necessary functions for processing a drive file"""
    drive_file = DriveFile.objects.get(file_id=drive_file_id)
    try:
        api.stream_to_s3(drive_file)
        if drive_file.is_video():
            api.transcode_gdrive_video(drive_file)
        api.create_gdrive_resource_content(drive_file)
    except:  # pylint:disable=bare-except
        log.exception("Error processing DriveFile %s", drive_file_id)


@app.task()
def delete_drive_file(drive_file_id: str):
    """
    Delete the DriveFile if it is not being used in website page content.
    See api.delete_drive_file for details.
    """
    drive_file = DriveFile.objects.filter(file_id=drive_file_id).first()
    if drive_file:
        api.delete_drive_file(drive_file)


@app.task(bind=True)
@single_task(timeout=settings.DRIVE_IMPORT_RECENT_FILES_SECONDS, raise_block=False)
def import_recent_files(self, last_dt: str = None):  # pylint: disable=too-many-locals
    """
    Query the Drive API for recently uploaded or modified files and process them
    if they are in folders that match Website short_ids or names.
    """
    if (
        not api.is_gdrive_enabled()
        or settings.DRIVE_IMPORT_RECENT_FILES_SECONDS is None
    ):
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

    tasks = []
    website_names = set()
    for gdfile in api.query_files(query=query, fields=DRIVE_FILE_FIELDS):
        try:
            drive_file = api.process_file_result(gdfile)
            if drive_file:
                maxLastTime = datetime.strptime(
                    max(gdfile.get("createdTime"), gdfile.get("modifiedTime")),
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=pytz.utc)
                if not last_checked or maxLastTime > last_checked:
                    last_checked = maxLastTime
                tasks.append(process_drive_file.s(drive_file.file_id))
                website_names.add(drive_file.website.name)
        except:  # pylint:disable=bare-except
            log.exception("Error processing google drive file %s", gdfile.get("id"))

    file_token_obj.last_dt = last_checked
    file_token_obj.save()

    if tasks:
        # Import the files first, then sync the websites for those files in git
        file_steps = chord(celery.group(*tasks), chord_finisher.si())
        website_steps = [
            sync_website_content.si(website_name) for website_name in website_names
        ]
        workflow = chain(file_steps, celery.group(website_steps))
        raise self.replace(celery.group(workflow))


def _get_gdrive_files(website: Website) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """
    Returns a tuple (files, errors).

    `files` is a dict where keys are subfolder names and value is a
    list of file objects.
    `errors` is a list of errors while fetching files.
    """
    errors = []
    gDriveSubfolderFiles = {}

    for subfolder in [DRIVE_FOLDER_FILES_FINAL, DRIVE_FOLDER_VIDEOS_FINAL]:
        try:
            query = f'parents = "{website.gdrive_folder}" and name="{subfolder}" and mimeType = "{DRIVE_MIMETYPE_FOLDER}" and not trashed'
            subfolder_list = list(
                api.query_files(query=query, fields=DRIVE_FILE_FIELDS)
            )
            if not subfolder_list:
                error_msg = f"Could not find drive subfolder {subfolder}"
                log.error("%s for %s", error_msg, website.short_id)
                errors.append(error_msg)
                continue

            gDriveSubfolderFiles[subfolder] = list(
                api.walk_gdrive_folder(
                    subfolder_list[0]["id"],
                    DRIVE_FILE_FIELDS,
                )
            )
        except:  # pylint:disable=bare-except
            error_msg = f"An error occurred when querying the {subfolder} google drive subfolder"
            errors.append(error_msg)
            log.exception("%s for %s", error_msg, website.short_id)

    return gDriveSubfolderFiles, errors


@app.task(bind=True, acks_late=True, autoretry_for=(BlockingIOError,), retry_backoff=30)
@single_task(30)
def import_website_files(self, name: str):
    """Query the Drive API for all children of a website folder and import the files"""
    if not api.is_gdrive_enabled():
        return
    website = Website.objects.get(name=name)
    website.sync_status = WebsiteSyncStatus.PROCESSING
    website.synced_on = now_in_utc()
    website.sync_errors = []

    gDriveSubfolderFiles, errors = _get_gdrive_files(website)

    deleted_drive_files = api.find_missing_files(
        sum(gDriveSubfolderFiles.values(), []), website
    )
    delete_file_tasks = [
        delete_drive_file.si(drive_file.file_id) for drive_file in deleted_drive_files
    ]

    file_tasks = []
    for gDriveFiles in gDriveSubfolderFiles.values():
        occurrences = Counter([file.get("name") for file in gDriveFiles])
        for gdfile in gDriveFiles:
            try:
                drive_file = api.process_file_result(
                    gdfile,
                    sync_date=website.synced_on,
                    name_occurrence_count=occurrences[gdfile.get("name")],
                )
                if drive_file:
                    file_tasks.append(process_drive_file.s(drive_file.file_id))
            except:  # pylint:disable=bare-except
                errors.append(f"Error processing gdrive file {gdfile.get('name')}")
                log.exception(
                    "Error processing gdrive file %s for %s",
                    gdfile.get("name"),
                    website.short_id,
                )
    website.sync_errors = errors
    website.save()

    workflow_steps = []

    if file_tasks:
        # Import the files first, then sync the website for those files in git
        step = chord(
            celery.group(*file_tasks),
            update_website_status.si(website.pk, website.synced_on),
        )
        workflow_steps.append(step)

    if delete_file_tasks:
        step = chord(celery.group(*delete_file_tasks), chord_finisher.si())
        workflow_steps.append(step)

    if workflow_steps:
        step = sync_website_content.si(name)
        workflow_steps.append(step)

        workflow = chain(*workflow_steps)
        raise self.replace(celery.group(workflow))
    update_website_status(website.pk, website.synced_on)


@app.task()
def create_gdrive_folders(website_short_id: str):
    """Create gdrive folder for website if it doesn't already exist"""
    if api.is_gdrive_enabled():
        api.create_gdrive_folders(website_short_id)


@app.task()
def create_gdrive_folders_batch(short_ids: List[str]):
    """Create Google Drive folders for a batch of websites"""
    errors = []
    for short_id in short_ids:
        try:
            api.create_gdrive_folders(short_id)
        except:  # pylint:disable=bare-except
            log.exception("Could not create google drive folders for %s", short_id)
            errors.append(short_id)
    return errors or True


@app.task(bind=True)
def create_gdrive_folders_chunked(self, short_ids: List[str], chunk_size=500):
    """Chunk and group batches of calls to create google drive folders for sites"""
    tasks = []
    for website_subset in chunks(
        sorted(short_ids),
        chunk_size=chunk_size,
    ):
        tasks.append(create_gdrive_folders_batch.s(website_subset))
    raise self.replace(celery.group(tasks))


@app.task
def update_website_status(website_pk: str, sync_dt: datetime):
    """
    Update the website gdrive sync status
    """
    api.update_sync_status(Website.objects.get(pk=website_pk), sync_dt)
