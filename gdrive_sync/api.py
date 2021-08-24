""" Google Drive API functions"""
import json
import logging
from datetime import datetime
from typing import Dict, List

import boto3
import pytz
import requests
from celery import chain
from django.conf import settings
from django.db.models import Q
from google.oauth2.service_account import (  # pylint:disable=no-name-in-module
    Credentials as ServiceAccountCredentials,
)
from googleapiclient.discovery import Resource, build

from gdrive_sync import tasks
from gdrive_sync.constants import DRIVE_API_FILES, DriveFileStatus
from gdrive_sync.models import DriveApiQueryTracker, DriveFile
from websites.models import Website


log = logging.getLogger(__name__)


def get_drive_service() -> Resource:
    """ Return a Google Drive service Resource"""
    key = json.loads(settings.DRIVE_SERVICE_ACCOUNT_CREDS)
    creds = ServiceAccountCredentials.from_service_account_info(
        key, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_file_list(query: str, fields: str) -> List[Dict]:
    """
    Get a list of Google Drive files filtered by an optional query and drive id.
    """
    service = get_drive_service()
    extra_kwargs = {}
    if settings.DRIVE_SHARED_ID:
        extra_kwargs["driveId"] = settings.DRIVE_SHARED_ID
        extra_kwargs["corpora"] = "drive"

    extra_kwargs["q"] = query
    files = []
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
        files.extend(file_response["files"])
        next_token = file_response.get("nextPageToken", None)
        if next_token:
            extra_kwargs["pageToken"] = next_token
        else:
            extra_kwargs.pop("pageToken", None)
    return files


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


def process_file_result(file_obj: Dict) -> bool:
    """Convert an API file response into DriveFile objects"""
    parents = file_obj.get("parents")
    if parents:
        folder_tree = get_parent_tree(parents)
        if (
            settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID
            and settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID
            not in [folder["id"] for folder in folder_tree]
        ):
            return

        for folder in folder_tree:
            website = Website.objects.filter(
                Q(short_id=folder["name"]) | Q(name=folder["name"])
            ).first()
            if website:
                existing_file = DriveFile.objects.filter(
                    file_id=file_obj.get("id")
                ).first()
                if existing_file and existing_file.checksum == file_obj.get(
                    "md5Checksum"
                ):
                    # For inexplicable reasons, sometimes Google Drive continuously updates
                    # the modifiedTime of files, so only update the DriveFile if the checksum changed.
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
                    },
                )
                # Kick off chained async celery tasks to transfer file to S3, then start a transcode job
                chain(
                    tasks.stream_drive_file_to_s3.s(drive_file.file_id),
                    tasks.transcode_drive_file_video.si(drive_file.file_id),
                )()
                return True
    log.error(
        "No matching website could be found for file %s (%s)",
        file_obj.get("name"),
        file_obj.get("fileId"),
    )
    return False


def import_recent_videos(last_dt=None):
    """
    Query the Drive API for recently uploaded or modified video files and process them
    if they are in folders that match Website short_ids or names.
    """
    file_token_obj, _ = DriveApiQueryTracker.objects.get_or_create(
        api_call=DRIVE_API_FILES
    )
    query = "(mimeType contains 'video/' and not trashed)"
    fields = "nextPageToken, files(id, name, md5Checksum, mimeType, createdTime, modifiedTime, webContentLink, trashed, parents)"
    last_checked = last_dt or file_token_obj.last_dt
    if last_checked:
        dt_str = last_checked.strftime("%Y-%m-%dT%H:%M:%S.%f")
        query += f" and (modifiedTime > '{dt_str}' or createdTime > '{dt_str}')"

    videos = get_file_list(query=query, fields=fields)
    for video in videos:
        if process_file_result(video):
            maxLastTime = datetime.strptime(
                max(video.get("createdTime"), video.get("modifiedTime")),
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=pytz.utc)
            if not last_checked or maxLastTime > last_checked:
                last_checked = maxLastTime
    file_token_obj.last_dt = last_checked
    file_token_obj.save()


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
    try:
        s3 = boto3.resource("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        bucket = s3.Bucket(bucket_name)

        drive_file.update_status(DriveFileStatus.UPLOADING)
        drive_file.s3_key = "/".join(
            [
                settings.DRIVE_S3_UPLOAD_PREFIX,
                drive_file.website.short_id,
                drive_file.file_id,
                drive_file.name,
            ]
        )
        bucket.upload_fileobj(
            Fileobj=streaming_download(drive_file).raw,
            Key=drive_file.s3_key,
            ExtraArgs={"ContentType": drive_file.mime_type, "ACL": "public-read"},
        )
        drive_file.update_status(DriveFileStatus.UPLOAD_COMPLETE)
    except:  # pylint:disable=bare-except
        drive_file.update_status(DriveFileStatus.UPLOAD_FAILED)
        raise
    finally:
        service.permissions().delete(
            supportsAllDrives=True,
            permissionId=permission["id"],
            fileId=drive_file.file_id,
        ).execute()


def create_gdrive_folder_if_not_exists(website_short_id: str, website_name: str):
    """Create gdrive folder for website if it doesn't already exist"""
    query = f"(mimeType = 'application/vnd.google-apps.folder') and not trashed and (name = '{website_short_id}' or name = '{website_name}')"

    fields = "nextPageToken, files(id, name, parents)"
    folders = get_file_list(query=query, fields=fields)

    if settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID:
        filtered_folders = []
        for folder in folders:
            ancestors = get_parent_tree(folder["parents"])

            if settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID in [
                ancestor["id"] for ancestor in ancestors
            ]:
                filtered_folders.append(folder)

    else:
        filtered_folders = folders

    if len(filtered_folders) == 0:
        service = get_drive_service()

        file_metadata = {
            "name": website_short_id,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID:
            file_metadata["parents"] = [settings.DRIVE_VIDEO_UPLOADS_PARENT_FOLDER_ID]
        else:
            file_metadata["parents"] = [settings.DRIVE_SHARED_ID]

        return (
            service.files()
            .create(supportsAllDrives=True, body=file_metadata, fields="id")
            .execute()
        )
