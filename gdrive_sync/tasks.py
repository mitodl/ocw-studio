"""gdrive_sync tasks"""
import logging
from datetime import datetime
from typing import List

import celery
from celery import chain, chord
from mitol.common.utils import chunks, now_in_utc

from content_sync.decorators import single_task
from content_sync.tasks import sync_website_content
from gdrive_sync import api
from gdrive_sync.constants import (
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    WebsiteSyncStatus,
)
from gdrive_sync.models import DriveFile
from main.celery import app
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
    errors = []
    tasks = []
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
            for gdfile in api.walk_gdrive_folder(
                subfolder_list[0]["id"],
                DRIVE_FILE_FIELDS,
            ):
                try:
                    drive_file = api.process_file_result(
                        gdfile, website, sync_date=website.synced_on
                    )
                    if drive_file:
                        tasks.append(process_drive_file.s(drive_file.file_id))
                except:  # pylint:disable=bare-except
                    errors.append(f"Error processing gdrive file {gdfile.get('name')}")
                    log.exception(
                        "Error processing gdrive file %s for %s",
                        gdfile.get("name"),
                        website.short_id,
                    )
        except:  # pylint:disable=bare-except
            error_msg = f"An error occurred when querying the {subfolder} google drive subfolder"
            errors.append(error_msg)
            log.exception("%s for %s", error_msg, website.short_id)
    website.sync_errors = errors
    website.save()

    if tasks:
        # Import the files first, then sync the website for those files in git
        file_steps = chord(
            celery.group(*tasks),
            update_website_status.si(website.pk, website.synced_on),
        )
        website_step = sync_website_content.si(name)
        workflow = chain(file_steps, website_step)
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
