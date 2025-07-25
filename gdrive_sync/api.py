"""Google Drive API functions"""

import io
import json
import logging
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from boto3.s3.transfer import TransferConfig
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from google.oauth2.service_account import (  # pylint:disable=no-name-in-module
    Credentials as ServiceAccountCredentials,
)
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from content_sync.api import get_sync_backend
from content_sync.decorators import retry_on_failure
from gdrive_sync.constants import (
    DRIVE_FILE_CREATED_TIME,
    DRIVE_FILE_DOWNLOAD_LINK,
    DRIVE_FILE_ID,
    DRIVE_FILE_MD5_CHECKSUM,
    DRIVE_FILE_MIME_TYPE,
    DRIVE_FILE_MODIFIED_TIME,
    DRIVE_FILE_NAME,
    DRIVE_FILE_SIZE,
    DRIVE_FOLDER_FILES,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    VALID_TEXT_FILE_TYPES,
    DriveFileStatus,
    WebsiteSyncStatus,
)
from gdrive_sync.models import DriveFile
from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename
from videos.api import create_media_convert_job
from videos.constants import VideoJobStatus, VideoStatus
from videos.models import Video, VideoJob
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
from websites.utils import get_valid_base_filename

log = logging.getLogger(__name__)


class GDriveStreamReader:
    """Read a Gdrive media file as bytes via the API"""

    def __init__(self, drive_file: DriveFile):
        """Initialize the object with a DriveFile"""
        self.service = get_drive_service()
        self.request = self.service.files().get_media(
            fileId=drive_file.file_id, supportsAllDrives=True
        )
        self.fh = io.BytesIO()
        self.downloader = MediaIoBaseDownload(self.fh, self.request)
        self.done = False

    def read(self, amount: int | None = None):
        """Read and return the next chunk of bytes from the GDrive file"""
        if amount:
            # Make sure the chunksize is the same as what's requested by boto3
            self.downloader._chunksize = (  # noqa: SLF001
                amount  # pylint:disable=protected-access
            )
        if self.done is False:
            self.fh.seek(0)
            self.fh.truncate()
            _, self.done = self.downloader.next_chunk()
            self.fh.seek(0)
            return self.fh.read()
        return b""


def get_drive_service() -> Resource:
    """Return a Google Drive service Resource"""
    key = json.loads(settings.DRIVE_SERVICE_ACCOUNT_CREDS)
    creds = ServiceAccountCredentials.from_service_account_info(
        key, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def query_files(query: str, fields: str) -> Iterable[dict]:
    """
    Get a list of Google Drive files filtered by an optional query and drive id.
    """
    service = get_drive_service()
    extra_kwargs = {}
    if settings.DRIVE_SHARED_ID:
        extra_kwargs["driveId"] = settings.DRIVE_SHARED_ID
        extra_kwargs["corpora"] = "drive"

    extra_kwargs["q"] = query
    next_token = "initial"  # noqa: S105
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
        yield from file_response["files"]


def _get_or_create_drive_file(
    file_obj: dict,
    drive_path: str,
    website: Website,
    sync_date: datetime | None,
    replace_file: bool = True,  # noqa: FBT001, FBT002
) -> DriveFile | None:
    """
    Determines if `file_obj` is a new or updated file and returns a new or updated
    DriveFile respectively.
    Returns None if no change is detected.
    """  # noqa: D401
    existing_file_same_id = DriveFile.objects.filter(
        file_id=file_obj.get(DRIVE_FILE_ID)
    ).first()
    if (
        existing_file_same_id
        and existing_file_same_id.checksum == file_obj.get(DRIVE_FILE_MD5_CHECKSUM, "")
        and existing_file_same_id.name == file_obj.get(DRIVE_FILE_NAME, "")
        and existing_file_same_id.status
        in (
            DriveFileStatus.COMPLETE,
            DriveFileStatus.UPLOADING,
            DriveFileStatus.UPLOAD_COMPLETE,
            DriveFileStatus.TRANSCODING,
        )
    ):
        # For inexplicable reasons, sometimes Google Drive continuously updates
        # the modifiedTime of files, so only update the DriveFile if the checksum or name changed,  # noqa: E501
        # and the status indicates that the file processing is not complete or in progress.  # noqa: E501
        return None

    file_data = {
        "drive_path": drive_path,
        "name": file_obj.get(DRIVE_FILE_NAME),
        "website": website,
        "mime_type": file_obj.get(DRIVE_FILE_MIME_TYPE),
        "checksum": file_obj.get(DRIVE_FILE_MD5_CHECKSUM),
        "modified_time": file_obj.get(DRIVE_FILE_MODIFIED_TIME),
        "created_time": file_obj.get(DRIVE_FILE_CREATED_TIME),
        "size": file_obj.get(DRIVE_FILE_SIZE),
        "download_link": file_obj.get(DRIVE_FILE_DOWNLOAD_LINK),
        "sync_error": None,
        "sync_dt": sync_date,
    }

    if existing_file_same_id:
        for k, v in file_data.items():
            setattr(existing_file_same_id, k, v)
        existing_file_same_id.save()
        drive_file = existing_file_same_id
    else:
        existing_file_same_path = DriveFile.objects.filter(
            drive_path=drive_path,
            name=file_obj.get(DRIVE_FILE_NAME),
            website=website,
        ).first()

        file_data.update({"file_id": file_obj.get(DRIVE_FILE_ID)})

        if replace_file and existing_file_same_path:
            # A drive file already exists on the same path.
            # We'll detach the resource from this one and attach it
            # to a new DriveFile.
            file_data.update(
                {
                    "resource": existing_file_same_path.resource,
                }
            )
            existing_file_same_path.resource = None
            existing_file_same_path.save()
            delete_drive_file(existing_file_same_path, sync_date)

        drive_file = DriveFile.objects.create(**file_data)
    return drive_file


def get_parent_tree(parents):
    """Return a list of parent folders"""
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
    file_obj: dict,
    website: Website,
    sync_date: datetime | None = None,
    *,
    replace_file: bool | None = True,
) -> DriveFile | None:
    """
    Convert an API file response into a DriveFile object.

    Args:
        file_obj (dict): A GDrive file object.
        sync_date (datetime, optional): Time of sync. Defaults to None.
        replace_file (bool, optional):
            Whether or not to replace the file that has the same internal path as file_obj.
            Defaults to True.

    Returns:
        Optional[DriveFile]: A DriveFile object that corresponds to `file_obj`.
            None for files that are ineligible or have not changed.
    """  # noqa: E501
    parents = file_obj.get("parents")
    if parents:
        folder_tree = get_parent_tree(parents)
        if len(folder_tree) < 2 or (  # noqa: PLR2004
            settings.DRIVE_UPLOADS_PARENT_FOLDER_ID
            and (
                settings.DRIVE_UPLOADS_PARENT_FOLDER_ID
                not in [folder["id"] for folder in folder_tree]
            )
        ):
            return None

        folder_names = [folder["name"] for folder in folder_tree]
        in_video_folder = DRIVE_FOLDER_VIDEOS_FINAL in folder_names
        in_file_folder = DRIVE_FOLDER_FILES_FINAL in folder_names
        is_video = file_obj[DRIVE_FILE_MIME_TYPE].lower().startswith("video/")
        processable = (
            ((in_video_folder and is_video) or in_file_folder)
            and file_obj.get(DRIVE_FILE_DOWNLOAD_LINK) is not None
            and file_obj.get(DRIVE_FILE_MD5_CHECKSUM) is not None
        )

        if website and processable:
            drive_path = "/".join([folder.get("name") for folder in folder_tree])
            return _get_or_create_drive_file(
                file_obj=file_obj,
                drive_path=drive_path,
                website=website,
                sync_date=sync_date,
                replace_file=replace_file,
            )
    return None


@retry_on_failure
def stream_to_s3(drive_file: DriveFile):
    """Stream a Google Drive file to S3"""
    if drive_file.status in (
        DriveFileStatus.UPLOAD_COMPLETE,
        DriveFileStatus.TRANSCODING,
        DriveFileStatus.COMPLETE,
    ):
        return
    try:
        s3 = get_boto3_resource("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        bucket = s3.Bucket(bucket_name)
        if not drive_file.s3_key:
            drive_file.s3_key = drive_file.get_valid_s3_key()
        drive_file.update_status(DriveFileStatus.UPLOADING)
        extra_args = {"ContentType": drive_file.mime_type, "ACL": "public-read"}

        if drive_file.mime_type.startswith("video/"):
            extra_args["ContentDisposition"] = "attachment"

        config = TransferConfig(
            multipart_chunksize=64 * 1024 * 1024,  # 64 MB chunks
            max_concurrency=5,
        )
        bucket.upload_fileobj(
            Fileobj=GDriveStreamReader(drive_file),
            Key=drive_file.s3_key,
            ExtraArgs=extra_args,
            Config=config,
        )
        drive_file.update_status(DriveFileStatus.UPLOAD_COMPLETE)
    except Exception as exc:
        log.exception(
            "An error occurred uploading Google Drive file %s to S3",
            drive_file.name,
        )
        drive_file.sync_error = f"An error occurred uploading Google Drive file {drive_file.name} to S3: {exc}"  # noqa: E501
        drive_file.update_status(DriveFileStatus.UPLOAD_FAILED)
        raise


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
    s3 = get_boto3_resource("s3")
    bucket = s3.Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)
    return bucket.Object(key).content_type


def get_resource_type(drive_file: DriveFile) -> str:
    """Guess the resource type from S3 content_type or extension"""
    content_type = get_s3_content_type(drive_file.s3_key)
    _, extension = os.path.splitext(drive_file.s3_key)  # noqa: PTH122
    if content_type.startswith("image"):
        return RESOURCE_TYPE_IMAGE
    if (
        content_type.startswith("video")
        and DRIVE_FOLDER_VIDEOS_FINAL in drive_file.drive_path
    ):
        return RESOURCE_TYPE_VIDEO
    if content_type.startswith("text") or extension in VALID_TEXT_FILE_TYPES:
        return RESOURCE_TYPE_DOCUMENT
    return RESOURCE_TYPE_OTHER


def is_gdrive_enabled():
    """Determine if Gdrive integration is enabled via required settings"""
    return (
        settings.DRIVE_SHARED_ID is not None and len(settings.DRIVE_SHARED_ID) > 0
    ) and (settings.DRIVE_SERVICE_ACCOUNT_CREDS is not None)


def gdrive_root_url():
    """Get the root url of the Google Drive"""
    if is_gdrive_enabled():
        folder = (
            f"{settings.DRIVE_UPLOADS_PARENT_FOLDER_ID or settings.DRIVE_SHARED_ID}/"
        )
        return f"https://drive.google.com/drive/folders/{folder}"
    return None


def walk_gdrive_folder(folder_id: str, fields: str) -> Iterable[dict]:
    """Yield a list of all files under a Google Drive folder and its subfolders"""
    query = f'parents = "{folder_id}" and not trashed'
    drive_results = query_files(query=query, fields=fields)
    for result in drive_results:
        if result["mimeType"] != DRIVE_MIMETYPE_FOLDER:
            yield result
        else:
            yield from walk_gdrive_folder(result["id"], fields)


def get_pdf_title(drive_file: DriveFile) -> str:
    """Get the title of a PDF from its metadata, if available"""
    with io.BytesIO(GDriveStreamReader(drive_file).read()) as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        pdf_metadata = pdf_reader.metadata
        if pdf_metadata and "/Title" in pdf_metadata and pdf_metadata["/Title"] != "":
            return pdf_metadata["/Title"]
        return drive_file.name


@transaction.atomic
def create_gdrive_resource_content(drive_file: DriveFile):
    """Create a WebsiteContent resource from a Google Drive file"""
    try:
        resource_type = get_resource_type(drive_file)
        resource = drive_file.resource
        basename, extension = os.path.splitext(drive_file.name)  # noqa: PTH122
        basename = f"{basename}_{extension.lstrip('.')}"
        if not resource:
            site_config = SiteConfig(drive_file.website.starter.config)
            config_item = site_config.find_item_by_name(name=CONTENT_TYPE_RESOURCE)
            dirpath = config_item.file_target if config_item else None

            filename = get_valid_new_filename(
                website_pk=drive_file.website.pk,
                dirpath=dirpath,
                filename_base=slugify(
                    get_valid_base_filename(basename, CONTENT_TYPE_RESOURCE),
                    allow_unicode=True,
                ),
            )
            resource_type_fields = {
                "file_type": drive_file.mime_type,
                "file_size": drive_file.size,
                **dict.fromkeys(settings.RESOURCE_TYPE_FIELDS, resource_type),
            }

            resource_title = (
                get_pdf_title(drive_file)
                if extension.lower() == ".pdf"
                else drive_file.name
            )

            resource = WebsiteContent.objects.create(
                website=drive_file.website,
                title=resource_title,
                file=drive_file.s3_key,
                type=CONTENT_TYPE_RESOURCE,
                is_page_content=True,
                dirpath=dirpath,
                filename=filename,
                metadata={
                    **SiteConfig(
                        drive_file.website.starter.config
                    ).generate_item_metadata(
                        CONTENT_TYPE_RESOURCE,
                        cls=WebsiteContent,
                        use_defaults=True,
                        values=resource_type_fields,
                    )
                },
            )
        else:
            resource.file = drive_file.s3_key
            if resource.metadata.get("file_size") != drive_file.size:
                resource.metadata["file_size"] = drive_file.size
            if extension.lower() == ".pdf":
                # update resource title if PDF metadata contains title
                pdf_title = get_pdf_title(drive_file)
                if pdf_title != drive_file.name:
                    resource.title = pdf_title
            resource.save()
        drive_file.resource = resource
        drive_file.update_status(DriveFileStatus.COMPLETE)
    except PdfReadError:
        log.exception(
            "Could not create a resource from Google Drive file %s because it is not a valid PDF",  # noqa: E501
            drive_file.file_id,
        )
        drive_file.sync_error = f"Could not create a resource from Google Drive file {drive_file.name} because it is not a valid PDF"  # noqa: E501
        drive_file.update_status(DriveFileStatus.FAILED)
    except:  # pylint:disable=bare-except  # noqa: E722
        log.exception("Error creating resource for drive file %s", drive_file.file_id)
        drive_file.sync_error = (
            f"Could not create a resource from Google Drive file {drive_file.name}"
        )
        drive_file.update_status(DriveFileStatus.FAILED)


@retry_on_failure
def transcode_gdrive_video(drive_file: DriveFile):
    """Create a MediaConvert transcode job and Video object for the given drive file id if one doesn't already exist"""  # noqa: E501
    if settings.AWS_ACCOUNT_ID and settings.AWS_REGION and settings.AWS_ROLE_NAME:
        video, _ = Video.objects.get_or_create(
            source_key=drive_file.s3_key,
            website=drive_file.website,
            defaults={"status": VideoStatus.CREATED},
        )
        prior_job = (
            VideoJob.objects.filter(video=video)
            .exclude(status__in=(VideoJobStatus.FAILED, VideoJobStatus.COMPLETE))
            .first()
        )
        if prior_job:
            # Don't start another transcode job if there's a prior one that hasn't failed/completed yet  # noqa: E501
            return
        try:
            drive_file.video = video
            drive_file.save()
            create_media_convert_job(video)
            drive_file.update_status(DriveFileStatus.TRANSCODING)
        except Exception as exc:
            log.exception("Error creating transcode job for %s", video.source_key)
            video.status = VideoStatus.FAILED
            video.save()
            drive_file.sync_error = f"Error transcoding video {drive_file.name}: {exc}"
            drive_file.update_status(DriveFileStatus.TRANSCODE_FAILED)
            raise


def update_sync_status(website: Website, sync_datetime: datetime):
    """Update the Google Drive sync status based on DriveFile statuses and sync errors"""  # noqa: E501
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


@transaction.atomic
def rename_file(obj_text_id, obj_new_filename):
    """Rename the file on S3 associated with the WebsiteContent object to a new filename."""  # noqa: E501
    obj = WebsiteContent.objects.get(text_id=obj_text_id)
    site = obj.website
    df = DriveFile.objects.get(resource=obj)
    s3 = get_boto3_resource("s3")
    # slugify just the provided name and then make the extensions lowercase
    filepath = Path(obj_new_filename)
    new_filename = slugify(
        obj_new_filename.rstrip("".join(filepath.suffixes)), allow_unicode=True
    )
    if filepath.suffixes:
        new_filename += "".join(filepath.suffixes).lower()
    df_path = df.s3_key.split("/")
    df_path[-1] = new_filename
    new_key = "/".join(df_path)
    # check if an object with the new filename already exists in this course
    existing_obj = WebsiteContent.objects.filter(Q(website=site) & Q(file=new_key))
    if existing_obj:
        old_obj = existing_obj.first()
        if old_obj == obj:
            msg = "New filename is the same as the existing filename."
            raise ValueError(msg)
        dependencies = old_obj.get_content_dependencies()
        if dependencies:
            raise ValueError(
                "Not renaming file due to dependencies in existing content: "
                + str(dependencies)
            )

        log.info("Found existing file with same name. Overwriting it.")
        old_obj.delete()
        backend = get_sync_backend(site)
        backend.sync_all_content_to_backend()

    old_key = df.s3_key
    df.s3_key = new_key
    obj.file = new_key
    obj.filename = get_dirpath_and_filename(new_filename)[1]
    df.save()
    obj.save()

    s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_key).copy_from(
        CopySource=settings.AWS_STORAGE_BUCKET_NAME + "/" + old_key
    )
    s3.Object(settings.AWS_STORAGE_BUCKET_NAME, old_key).delete()


def find_missing_files(
    gDriveFiles: Iterable[dict], website: Website
) -> Iterable[DriveFile]:
    """
    Finds files that exist in the database but not in gDriveFiles. Uses the file_id attribute.

    Args:
        gDriveFiles (Iterable[Dict]): List of GDrive files, as returned by the files API.
        website (Website): The website being synced.

    Returns:
        Iterable[DriveFile]: DriveFile objects that exist in our database but not in `gDriveFiles`.
    """  # noqa: D401, E501
    gdrive_file_ids = [f["id"] for f in gDriveFiles]
    drive_files = DriveFile.objects.filter(website=website)
    return [file for file in drive_files if file.file_id not in gdrive_file_ids]


def delete_drive_file(drive_file: DriveFile, sync_datetime: datetime):
    """
    Deletes `drive_file` only if it is not being used in a page type content.

    Args:
        drive_file (DriveFile): A drive file.
    """  # noqa: D401
    dependencies = drive_file.get_content_dependencies()

    if dependencies:
        error_message = f"Cannot delete file {drive_file} because it is being used by {dependencies}."  # noqa: E501
        log.info(error_message)
        drive_file.sync_error = error_message
        drive_file.sync_dt = sync_datetime
        drive_file.save()
        return

    log.info("Deleting file %s", drive_file)

    if drive_file.resource:
        log.info("Deleting resource %s", drive_file.resource)
        drive_file.resource.delete()

    if drive_file.video:
        log.info("Deleting video %s", drive_file.video)
        drive_file.video.delete()

    drive_file.delete()
