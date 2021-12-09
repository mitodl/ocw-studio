""" Google Drive API functions"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Iterable, Optional

import boto3
import requests
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from google.oauth2.service_account import (  # pylint:disable=no-name-in-module
    Credentials as ServiceAccountCredentials,
)
from googleapiclient.discovery import Resource, build

from gdrive_sync.constants import (
    DRIVE_FOLDER_FILES,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    VALID_TEXT_FILE_TYPES,
    DriveFileStatus,
    WebsiteSyncStatus,
)
from gdrive_sync.models import DriveFile
from videos.api import create_media_convert_job
from videos.constants import VideoStatus
from videos.models import Video
from websites.api import get_valid_new_filename
from websites.constants import (
    CONTENT_TYPE_RESOURCE,
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_OTHER,
    RESOURCE_TYPE_VIDEO,
)
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig


log = logging.getLogger(__name__)


def get_drive_service() -> Resource:
    """ Return a Google Drive service Resource"""
    key = json.loads(settings.DRIVE_SERVICE_ACCOUNT_CREDS)
    creds = ServiceAccountCredentials.from_service_account_info(
        key, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def query_files(query: str, fields: str) -> Iterable[Dict]:
    """
    Get a list of Google Drive files filtered by an optional query and drive id.
    """
    service = get_drive_service()
    extra_kwargs = {}
    if settings.DRIVE_SHARED_ID:
        extra_kwargs["driveId"] = settings.DRIVE_SHARED_ID
        extra_kwargs["corpora"] = "drive"

    extra_kwargs["q"] = query
    next_token = "initial"
    while next_token is not None:
        file_response = (
            service.files()
            .list(
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields=fields,
                **extra_kwargs,
            )
            .execute()
        )
        next_token = file_response.get("nextPageToken", None)
        if next_token:
            extra_kwargs["pageToken"] = next_token
        else:
            extra_kwargs.pop("pageToken", None)
        for file_obj in file_response["files"]:
            yield file_obj


def get_parent_tree(parents):
    """ Return a list of parent folders """
    service = get_drive_service()
    tree = []  # Result
    while True:
        folder = (
            service.files()
            .get(supportsAllDrives=True, fileId=parents[0], fields="id, name, parents")
            .execute()
        )
        tree.insert(0, {"id": parents[0], "name": folder.get("name")})
        parents = folder.get("parents")
        if not parents:
            break
    return tree[1:]  # first one is the drive


def process_file_result(
    file_obj: Dict, sync_date: Optional[datetime] = None
) -> Optional[DriveFile]:
    """Convert an API file response into a DriveFile object"""
    parents = file_obj.get("parents")
    if parents:
        folder_tree = get_parent_tree(parents)
        if len(folder_tree) < 2 or (
            settings.DRIVE_UPLOADS_PARENT_FOLDER_ID
            and (
                settings.DRIVE_UPLOADS_PARENT_FOLDER_ID
                not in [folder["id"] for folder in folder_tree]
            )
        ):
            return

        folder_names = [folder["name"] for folder in folder_tree]
        website = Website.objects.filter(short_id__in=folder_names).first()
        in_video_folder = DRIVE_FOLDER_VIDEOS_FINAL in folder_names
        in_file_folder = DRIVE_FOLDER_FILES_FINAL in folder_names
        is_video = file_obj["mimeType"].lower().startswith("video/")
        processable = (
            (in_video_folder and is_video) or (in_file_folder and not is_video)
        ) and file_obj.get("webContentLink") is not None
        if website and processable:
            existing_file = DriveFile.objects.filter(file_id=file_obj.get("id")).first()
            if (
                existing_file
                and existing_file.checksum == file_obj.get("md5Checksum", "")
                and existing_file.name == file_obj.get("name")
                and existing_file.status == DriveFileStatus.COMPLETE
            ):
                # For inexplicable reasons, sometimes Google Drive continuously updates
                # the modifiedTime of files, so only update the DriveFile if the checksum or name changed.
                return
            drive_file, _ = DriveFile.objects.update_or_create(
                file_id=file_obj.get("id"),
                defaults={
                    "name": file_obj.get("name"),
                    "mime_type": file_obj.get("mimeType"),
                    "checksum": file_obj.get("md5Checksum"),
                    "modified_time": file_obj.get("modifiedTime"),
                    "created_time": file_obj.get("createdTime"),
                    "download_link": file_obj.get("webContentLink"),
                    "drive_path": "/".join(
                        [folder.get("name") for folder in folder_tree]
                    ),
                    "website": website,
                    "sync_error": None,
                    "sync_dt": sync_date,
                },
            )
            return drive_file
    return None


def streaming_download(drive_file: DriveFile) -> requests.Response:
    """Return a streaming response for a drive file download URL"""

    def get_confirm_token(response: requests.Response) -> str:
        """ Get the confirmation token for downloading a large drive file """
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                return value
        return None

    session = requests.Session()
    extra_params = {}
    # make an initial request to get a confirmation token in the cookies if required
    response = session.get(
        drive_file.download_link,
        params=extra_params,
        stream=True,
    )
    token = get_confirm_token(response)
    if token:
        extra_params["confirm"] = token
    response = session.get(drive_file.download_link, params=extra_params, stream=True)
    return response


def stream_to_s3(drive_file: DriveFile):
    """ Stream a Google Drive file to S3 """
    service = None
    permission = None
    try:
        service = get_drive_service()
        permission = (
            service.permissions()
            .create(
                supportsAllDrives=True,
                body={"role": "reader", "type": "anyone"},
                fileId=drive_file.file_id,
            )
            .execute()
        )
        s3 = boto3.resource("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        bucket = s3.Bucket(bucket_name)
        if not drive_file.s3_key:
            drive_file.s3_key = drive_file.get_valid_s3_key()
        drive_file.update_status(DriveFileStatus.UPLOADING)
        extra_args = {"ContentType": drive_file.mime_type, "ACL": "public-read"}

        if drive_file.mime_type.startswith("video/"):
            extra_args["ContentDisposition"] = "attachment"

        bucket.upload_fileobj(
            Fileobj=streaming_download(drive_file).raw,
            Key=drive_file.s3_key,
            ExtraArgs=extra_args,
        )
        drive_file.update_status(DriveFileStatus.UPLOAD_COMPLETE)
    except:  # pylint:disable=bare-except
        drive_file.sync_error = (
            f"An error occurred uploading google drive file {drive_file.name} to S3"
        )
        drive_file.update_status(DriveFileStatus.UPLOAD_FAILED)
        raise
    finally:
        if service and permission:
            service.permissions().delete(
                supportsAllDrives=True,
                permissionId=permission["id"],
                fileId=drive_file.file_id,
            ).execute()


def create_gdrive_folders(website_short_id: str) -> bool:
    """Create gdrive folder for website if it doesn't already exist"""
    folder_created = False
    service = get_drive_service()
    base_query = "mimeType = 'application/vnd.google-apps.folder' and not trashed and "
    query = f"{base_query}name = '{website_short_id}'"

    fields = "nextPageToken, files(id, name, parents)"
    folders = list(query_files(query=query, fields=fields))

    if settings.DRIVE_UPLOADS_PARENT_FOLDER_ID:
        filtered_folders = []
        for folder in folders:
            ancestors = get_parent_tree(folder["parents"])

            if settings.DRIVE_UPLOADS_PARENT_FOLDER_ID in [
                ancestor["id"] for ancestor in ancestors
            ]:
                filtered_folders.append(folder)

    else:
        filtered_folders = folders

    if len(filtered_folders) == 0:
        folder_metadata = {
            "name": website_short_id,
            "mimeType": DRIVE_MIMETYPE_FOLDER,
        }
        if settings.DRIVE_UPLOADS_PARENT_FOLDER_ID:
            folder_metadata["parents"] = [settings.DRIVE_UPLOADS_PARENT_FOLDER_ID]
        else:
            folder_metadata["parents"] = [settings.DRIVE_SHARED_ID]

        folder = (
            service.files()
            .create(supportsAllDrives=True, body=folder_metadata, fields="id")
            .execute()
        )
        folder_created = True
    else:
        folder = filtered_folders[0]

    Website.objects.filter(short_id=website_short_id).update(gdrive_folder=folder["id"])

    for subfolder in [
        DRIVE_FOLDER_FILES,
        DRIVE_FOLDER_FILES_FINAL,
        DRIVE_FOLDER_VIDEOS_FINAL,
    ]:
        query = f"{base_query}name = '{subfolder}' and parents = '{folder['id']}'"
        folders = list(query_files(query=query, fields=fields))
        if len(folders) == 0:
            folder_metadata = {
                "name": subfolder,
                "mimeType": DRIVE_MIMETYPE_FOLDER,
                "parents": [folder["id"]],
            }
            service.files().create(
                supportsAllDrives=True, body=folder_metadata, fields="id"
            ).execute()
            folder_created = True
    return folder_created


def get_s3_content_type(key: str) -> str:
    """Return the S3 object content_type"""
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)
    return bucket.Object(key).content_type


def get_resource_type(key: str) -> str:
    """ Guess the resource type from S3 content_type or extension"""
    content_type = get_s3_content_type(key)
    _, extension = os.path.splitext(key)
    if content_type.startswith("image"):
        return RESOURCE_TYPE_IMAGE
    if content_type.startswith("video"):
        return RESOURCE_TYPE_VIDEO
    if content_type.startswith("text") or extension in VALID_TEXT_FILE_TYPES:
        return RESOURCE_TYPE_DOCUMENT
    return RESOURCE_TYPE_OTHER


def is_gdrive_enabled():
    """Determine if Gdrive integration is enabled via required settings"""
    return settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS


def gdrive_root_url():
    """Get the root url of the Google Drive"""
    if is_gdrive_enabled():
        folder = (
            f"{settings.DRIVE_UPLOADS_PARENT_FOLDER_ID or settings.DRIVE_SHARED_ID}/"
        )
        return f"https://drive.google.com/drive/folders/{folder}"


def walk_gdrive_folder(folder_id: str, fields: str) -> Iterable[Dict]:
    """ Yield a list of all files under a Google Drive folder and its subfolders"""
    query = f'parents = "{folder_id}" and not trashed'
    drive_results = query_files(query=query, fields=fields)
    for result in drive_results:
        if result["mimeType"] != DRIVE_MIMETYPE_FOLDER:
            yield result
        else:
            for sub_result in walk_gdrive_folder(result["id"], fields):
                yield sub_result


@transaction.atomic
def create_gdrive_resource_content(drive_file: DriveFile):
    """Create a WebsiteContent resource from a Google Drive file"""
    try:
        resource_type = get_resource_type(drive_file.s3_key)
        resource = drive_file.resource
        if not resource:
            site_config = SiteConfig(drive_file.website.starter.config)
            config_item = site_config.find_item_by_name(name="resource")
            dirpath = config_item.file_target if config_item else None
            basename, _ = os.path.splitext(drive_file.name)
            filename = get_valid_new_filename(
                website_pk=drive_file.website.pk,
                dirpath=dirpath,
                filename_base=slugify(basename),
            )
            resource = WebsiteContent.objects.create(
                website=drive_file.website,
                title=drive_file.name,
                file=drive_file.s3_key,
                type="resource",
                is_page_content=True,
                dirpath=dirpath,
                filename=filename,
                metadata={
                    **SiteConfig(
                        drive_file.website.starter.config
                    ).generate_item_metadata(CONTENT_TYPE_RESOURCE, cls=WebsiteContent),
                    "resourcetype": resource_type,
                    "file_type": drive_file.mime_type,
                },
            )
        else:
            resource.file = drive_file.s3_key
            resource.save()
        drive_file.resource = resource
        drive_file.update_status(DriveFileStatus.COMPLETE)
    except:  # pylint:disable=bare-except
        log.exception("Error creating resource for drive file %s", drive_file.file_id)
        drive_file.sync_error = (
            f"Could not create a resource from google drive file {drive_file.name}"
        )
        drive_file.update_status(DriveFileStatus.FAILED)


def transcode_gdrive_video(drive_file: DriveFile):
    """Create a MediaConvert transcode job and Video object for the given drive file id"""
    if settings.AWS_ACCOUNT_ID and settings.AWS_REGION and settings.AWS_ROLE_NAME:
        video, _ = Video.objects.get_or_create(
            source_key=drive_file.s3_key,
            website=drive_file.website,
            defaults={"status": VideoStatus.CREATED},
        )
        drive_file.video = video
        drive_file.save()
        try:
            create_media_convert_job(video)
            drive_file.update_status(DriveFileStatus.TRANSCODING)
        except ClientError:
            log.exception("Error creating transcode job for %s", video.source_key)
            video.status = VideoStatus.FAILED
            video.save()
            drive_file.sync_error = f"Error transcoding video {drive_file.name}, please contact us for assistance"
            drive_file.update_status(DriveFileStatus.TRANSCODE_FAILED)
            raise


def update_sync_status(website: Website, sync_datetime: datetime):
    """Update the Google Drive sync status based on DriveFile statuses and sync errors"""
    drive_files = DriveFile.objects.filter(website=website, sync_dt=sync_datetime)
    resources = []
    errors = []
    statuses = []

    for drive_file in drive_files:
        statuses.append(drive_file.status)
        if drive_file.resource is not None:
            resources.append(drive_file.resource_id)
        if drive_file.sync_error is not None:
            errors.append(drive_file.sync_error)
    if (
        list(set(statuses)) == [DriveFileStatus.COMPLETE]
        and not errors
        and not website.sync_errors
    ):  # Resources created for all DriveFiles, no website errors
        new_status = WebsiteSyncStatus.COMPLETE
    elif (
        drive_files.count() == 0 and not website.sync_errors
    ):  # There was nothing to sync
        new_status = WebsiteSyncStatus.COMPLETE
    elif not resources or (resources and len(drive_files) == len(errors)):  # All failed
        new_status = WebsiteSyncStatus.FAILED
    else:  # Some failed, some did not
        new_status = WebsiteSyncStatus.ERRORS
        log.error(new_status)
    website.sync_status = new_status
    website.sync_errors = (website.sync_errors or []) + errors
    website.save()
