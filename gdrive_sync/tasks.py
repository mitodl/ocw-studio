"""gdrive_sync tasks"""
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import celery
from celery import chain, chord
from django.conf import settings
from mitol.common.utils import chunks, now_in_utc

from content_sync.api import upsert_content_sync_state
from content_sync.decorators import single_task
from content_sync.tasks import sync_website_content
from gdrive_sync import api, utils
from gdrive_sync.constants import (
    DRIVE_FILE_FIELDS,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    WebsiteSyncStatus,
)
from gdrive_sync.models import DriveFile
from main.celery import app
from main.s3_utils import get_boto3_resource
from main.tasks import chord_finisher
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.models import Website, WebsiteContent


# pylint:disable=unused-argument, raising-format-tuple


log = logging.getLogger(__name__)


@app.task()
def process_drive_file(drive_file_id: str):
    """
    Run the necessary functions for processing a drive file

    Returns:
        drive_file_id (str | None): Returns the `drive_file_id`, None
            if something goes wrong.
    """
    drive_file = DriveFile.objects.get(file_id=drive_file_id)
    try:
        api.stream_to_s3(drive_file)
        if drive_file.is_video():
            api.transcode_gdrive_video(drive_file)
        return drive_file_id
    except:  # pylint:disable=bare-except
        log.exception("Error processing DriveFile %s", drive_file_id)

    return None


@app.task()
def create_gdrive_resource_content_batch(drive_file_ids: List[Optional[str]]):
    """
    Creates WebsiteContent resources from a Google Drive files identified by `drive_file_ids`.

    `drive_file_ids` are expected to be results from `process_drive_file` tasks.
    """
    for drive_file_id in drive_file_ids:
        if drive_file_id is None:
            continue

        try:
            drive_file = DriveFile.objects.get(file_id=drive_file_id)
        except DriveFile.DoesNotExist as exc:
            log.exception(
                "Attempted to create resource for drive file %s which does not exist.",
                drive_file_id,
                exc_info=exc,
            )
        else:
            api.create_gdrive_resource_content(drive_file)


@app.task()
def delete_drive_file(drive_file_id: str, sync_datetime: datetime):
    """
    Delete the DriveFile if it is not being used in website page content.
    See api.delete_drive_file for details.
    """
    drive_file = DriveFile.objects.filter(file_id=drive_file_id).first()
    if drive_file:
        api.delete_drive_file(drive_file, sync_datetime=sync_datetime)


def _get_gdrive_files(website: Website) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """
    Returns a tuple (files, errors).

    `files` is a dict where keys are subfolder names and value is a
    list of file objects.
    `errors` is a list of errors while fetching files.
    """
    errors = []
    gdrive_subfolder_files = {}

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

            gdrive_subfolder_files[subfolder] = list(
                api.walk_gdrive_folder(
                    subfolder_list[0]["id"],
                    DRIVE_FILE_FIELDS,
                )
            )
        except:  # pylint:disable=bare-except
            error_msg = f"An error occurred when querying the {subfolder} google drive subfolder"
            errors.append(error_msg)
            log.exception("%s for %s", error_msg, website.short_id)

    return gdrive_subfolder_files, errors


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

    gdrive_subfolder_files, errors = _get_gdrive_files(website)

    deleted_drive_files = api.find_missing_files(
        sum(gdrive_subfolder_files.values(), []), website
    )
    delete_file_tasks = [
        delete_drive_file.si(drive_file.file_id, website.synced_on)
        for drive_file in deleted_drive_files
    ]

    file_tasks = []
    for gdrive_files in gdrive_subfolder_files.values():
        occurrences = Counter([file.get("name") for file in gdrive_files])
        for gdfile in gdrive_files:
            try:
                drive_file = api.process_file_result(
                    gdfile,
                    website=website,
                    sync_date=website.synced_on,
                    replace_file=occurrences[gdfile.get("name")] == 1,
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
        step = chord(
            celery.group(*file_tasks), create_gdrive_resource_content_batch.s()
        )
        workflow_steps.append(step)

    if delete_file_tasks:
        step = chord(celery.group(*delete_file_tasks), chord_finisher.si())
        workflow_steps.append(step)

    if workflow_steps:
        workflow_steps.append(update_website_status.si(website.pk, website.synced_on))
        workflow_steps.append(sync_website_content.si(name))
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


@app.task
def populate_file_sizes(website_name: str, override_existing: bool = False):
    """Populate all resource content of `website` with the `file_size` metadata field."""
    website = Website.objects.get(name=website_name)
    log.info("Starting file size population for %s.", website_name)

    updated_drive_files = []
    updated_contents = []

    s3 = get_boto3_resource("s3")
    bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)

    for content in website.websitecontent_set.filter(type=CONTENT_TYPE_RESOURCE):
        if not override_existing and content.metadata.get("file_size"):
            continue
        try:
            content.metadata["file_size"] = utils.fetch_content_file_size(
                content, bucket=bucket
            )
        except Exception as ex:  # pylint:disable=broad-except
            log.warning("Could not fetch file size for %s. %s", content, ex)
            content.metadata["file_size"] = None
        else:
            if content.metadata["file_size"] is None:
                log.info("Content %s has no file associated with it.", content)

        log.debug(
            "WebsiteContent %s now has file_size %s.",
            content,
            content.metadata["file_size"],
        )

        drive_files = content.drivefile_set.all()
        for drive_file in drive_files:
            if not override_existing and drive_file.size:
                continue

            try:
                drive_file.size = utils.fetch_drive_file_size(drive_file, bucket)
            except Exception as ex:  # pylint:disable=broad-except
                log.warning("Could not fetch file size for %s. %s", drive_file, ex)
            else:
                if drive_file.size is None:
                    log.info("DriveFile %s has no file associated to it.", drive_file)

            log.debug("DriveFile %s now has size %s.", drive_file, drive_file.size)

        updated_drive_files.extend(drive_files)
        updated_contents.append(content)

    DriveFile.objects.bulk_update(updated_drive_files, ["size"])
    WebsiteContent.objects.bulk_update(updated_contents, ["metadata"])

    # bulk_update does not call pre/post_save signals.
    # So we'll do the sync state update ourselves.
    for content in updated_contents:
        upsert_content_sync_state(content)

    website.has_unpublished_draft = True
    website.has_unpublished_live = True
    website.save()


@app.task(bind=True)
def populate_file_sizes_bulk(
    self, website_names: List[str], override_existing: bool = False
):
    """Run populate_file_sizes for `website_names` sequentially."""
    sub_tasks = [
        populate_file_sizes.si(name, override_existing) for name in website_names
    ]
    task_chain = chain(*sub_tasks)
    workflow = chord(task_chain, chord_finisher.si())
    raise self.replace(workflow)
