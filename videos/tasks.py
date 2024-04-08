"""Video tasks"""
import logging
from urllib.parse import urljoin

import celery
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from googleapiclient.errors import HttpError
from mitol.common.utils import now_in_utc
from mitol.mail.api import get_message_sender

from content_sync.decorators import single_task
from gdrive_sync.api import get_drive_service, query_files
from gdrive_sync.constants import (
    DRIVE_FILE_CREATED_TIME,
    DRIVE_FILE_DOWNLOAD_LINK,
    DRIVE_FILE_FIELDS,
    DRIVE_FILE_ID,
    DRIVE_FILE_MD5_CHECKSUM,
    DRIVE_FILE_MODIFIED_TIME,
    DRIVE_FILE_SIZE,
    DRIVE_FOLDER_FILES_FINAL,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DRIVE_MIMETYPE_FOLDER,
    DriveFileStatus,
)
from gdrive_sync.models import DriveFile
from gdrive_sync.utils import get_gdrive_file, get_resource_name
from main.celery import app
from main.constants import STATUS_CREATED
from main.s3_utils import get_boto3_resource
from videos import threeplay_api
from videos.constants import (
    DESTINATION_YOUTUBE,
    YT_THUMBNAIL_IMG,
    VideoFileStatus,
    VideoStatus,
    YouTubeStatus,
)
from videos.models import Video, VideoFile
from videos.utils import create_new_content
from videos.youtube import (
    API_QUOTA_ERROR_MSG,
    YouTubeApi,
    is_youtube_enabled,
    mail_youtube_upload_failure,
    mail_youtube_upload_success,
)
from websites.api import is_ocw_site, videos_missing_captions
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.messages import VideoTranscriptingCompleteMessage
from websites.models import Website, WebsiteContent
from websites.utils import get_dict_field, get_dict_query_field, set_dict_field

log = logging.getLogger()


@app.task
@single_task(timeout=settings.YT_UPLOAD_FREQUENCY, raise_block=False)
def upload_youtube_videos():
    """
    Upload public videos one at a time to YouTube (if not already there) until the daily maximum is reached.
    """  # noqa: E501
    if not is_youtube_enabled():
        return
    yt_queue = VideoFile.objects.filter(
        Q(destination=DESTINATION_YOUTUBE)
        & Q(destination_id__isnull=True)
        & Q(status=STATUS_CREATED)
    ).order_by("-created_on")[: settings.YT_UPLOAD_LIMIT]
    if yt_queue.count() == 0:
        return
    youtube = YouTubeApi()

    for video_file in yt_queue:
        error_msg = None
        try:
            response = youtube.upload_video(video_file)
            video_file.destination_id = response["id"]
            video_file.destination_status = response["status"]["uploadStatus"]
            video_file.status = VideoFileStatus.UPLOADED
        except HttpError as error:
            error_msg = error.content.decode("utf-8")
            if API_QUOTA_ERROR_MSG in error_msg:
                break
            log.exception("HttpError uploading video to Youtube: %s", video_file.s3_key)
            video_file.status = VideoFileStatus.FAILED
        except:  # pylint: disable=bare-except  # noqa: E722
            log.exception("Error uploading video to Youtube: %s", video_file.s3_key)
            video_file.status = VideoFileStatus.FAILED
        video_file.save()
        if error_msg:
            mail_youtube_upload_failure(video_file)


@app.task
def start_transcript_job(video_id: int):
    """
    If there are existing captions or transcript, associate them with the video;
    otherwise, use the 3Play API to order a new transcript for video
    """
    video = Video.objects.filter(pk=video_id).last()
    folder_name = video.website.short_id
    youtube_id = video.youtube_id()

    query_youtube_id_field = get_dict_query_field("metadata", settings.YT_FIELD_ID)

    video_resource = (
        WebsiteContent.objects.filter(website=video.website)
        .filter(Q(**{query_youtube_id_field: youtube_id}))
        .first()
    )

    captions, transcript = video.caption_transcript_resources()

    if captions or transcript:  # check for existing captions or transcript
        if captions:
            set_dict_field(
                video_resource.metadata, settings.YT_FIELD_CAPTIONS, captions.file.name
            )
        if transcript:
            set_dict_field(
                video_resource.metadata,
                settings.YT_FIELD_TRANSCRIPT,
                transcript.file.name,
            )
        video_resource.save()

    # if none and video is not already submitted, request a transcript through the 3Play API  # noqa: E501
    else:
        response = threeplay_api.threeplay_upload_video_request(
            folder_name, youtube_id, video_resource.title
        )

        threeplay_file_id = response.get("data").get("id")

        if (
            threeplay_file_id
            and video.status != VideoStatus.SUBMITTED_FOR_TRANSCRIPTION
        ):
            threeplay_api.threeplay_order_transcript_request(
                video.id, threeplay_file_id
            )
            video.status = VideoStatus.SUBMITTED_FOR_TRANSCRIPTION
            video.save()


@app.task(bind=True)
@single_task(timeout=settings.YT_STATUS_UPDATE_FREQUENCY, raise_block=False)
def update_youtube_statuses(self):  # noqa: C901
    """
    Update the status of recently uploaded YouTube videos if complete
    """
    if not is_youtube_enabled():
        return
    videos_processing = VideoFile.objects.filter(
        Q(status=VideoFileStatus.UPLOADED) & Q(destination=DESTINATION_YOUTUBE)
    )
    if videos_processing.count() == 0:
        return
    youtube = YouTubeApi()
    group_tasks = []
    for video_file in videos_processing:
        try:
            with transaction.atomic():
                video_file.destination_status = youtube.video_status(
                    video_file.destination_id
                )
                if video_file.destination_status == YouTubeStatus.PROCESSED:
                    video_file.status = VideoFileStatus.COMPLETE
                video_file.save()
                drive_file = DriveFile.objects.filter(video=video_file.video).first()
                if drive_file and drive_file.resource:
                    resource = drive_file.resource
                    set_dict_field(
                        resource.metadata,
                        settings.YT_FIELD_ID,
                        video_file.destination_id,
                    )
                    set_dict_field(
                        resource.metadata,
                        settings.YT_FIELD_THUMBNAIL,
                        YT_THUMBNAIL_IMG.format(video_id=video_file.destination_id),
                    )
                    resource.save()
                    if video_file.status == VideoFileStatus.COMPLETE:
                        group_tasks.append(start_transcript_job.s(video_file.video.id))
            if video_file.status == VideoFileStatus.COMPLETE:
                mail_youtube_upload_success(video_file)

        except IndexError:  # noqa: PERF203
            # Video might be a dupe or deleted, mark it as failed and continue to next one.  # noqa: E501
            video_file.status = VideoFileStatus.FAILED
            video_file.save()
            log.exception(
                "Status of YouTube video not found: youtube_id %s",
                video_file.destination_id,
            )
            mail_youtube_upload_failure(video_file)
        except HttpError as error:
            if API_QUOTA_ERROR_MSG in error.content.decode("utf-8"):
                # Don't raise the error, task will try on next run until daily quota is reset  # noqa: E501
                break
            log.exception(
                "Error for youtube_id %s: %s",
                video_file.destination_id,
                error.content.decode("utf-8"),
            )
            mail_youtube_upload_failure(video_file)

    if group_tasks:
        raise self.replace(celery.group(group_tasks))


@app.task(acks_late=True)
def remove_youtube_video(video_id):
    """
    Delete a video from Youtube
    """
    if not is_youtube_enabled():
        return
    try:
        YouTubeApi().delete_video(video_id)
    except HttpError as error:
        if error.resp.status == 404:  # noqa: PLR2004
            log.info("Not found on Youtube, already deleted?", video_id=video_id)
        else:
            raise


@app.task(acks_late=True)
def delete_s3_objects(
    key: str, as_filter: bool = False  # noqa: FBT001, FBT002
):  # pylint:disable=unused-argument
    """
    Delete objects from an S3 bucket
    """
    s3 = get_boto3_resource("s3")
    bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
    if not as_filter:
        bucket.delete_objects(Delete={"Objects": [{"Key": key}]})
    else:
        for obj in bucket.objects.filter(Prefix=key):
            obj.delete()


@app.task(acks_late=True)
@single_task(
    timeout=settings.UPDATE_TAGGED_3PLAY_TRANSCRIPT_FREQUENCY, raise_block=False
)
def update_transcripts_for_video(video_id: int):  # noqa: C901
    """Update transcripts for a video"""
    video = Video.objects.get(id=video_id)
    captions, transcript = video.caption_transcript_resources()
    has_threeplay_update = (
        False
        if captions or transcript
        else threeplay_api.update_transcripts_for_video(video)
    )
    if not captions and not transcript and not has_threeplay_update:
        return

    first_transcript_download = False

    if video.status != VideoStatus.COMPLETE:
        video.status = VideoStatus.COMPLETE
        video.save()
        if has_threeplay_update:
            first_transcript_download = True

    website = video.website
    if is_ocw_site(website):  # pylint: disable=too-many-nested-blocks
        search_fields = {}
        search_fields[
            get_dict_query_field("metadata", settings.FIELD_RESOURCETYPE)
        ] = RESOURCE_TYPE_VIDEO
        search_fields[
            get_dict_query_field("metadata", settings.YT_FIELD_ID)
        ] = video.youtube_id()

        for video_resource in website.websitecontent_set.filter(**search_fields):
            metadata = video_resource.metadata
            if has_threeplay_update:
                set_dict_field(
                    metadata,
                    settings.YT_FIELD_TRANSCRIPT,
                    urljoin(
                        "/",
                        video.pdf_transcript_file.name.replace(
                            video.website.s3_path, video.website.url_path
                        ),
                    ),
                )
                set_dict_field(
                    metadata,
                    settings.YT_FIELD_CAPTIONS,
                    urljoin(
                        "/",
                        video.webvtt_transcript_file.name.replace(
                            video.website.s3_path, video.website.url_path
                        ),
                    ),
                )
                video_resource.save()
            else:
                for resource, meta_field in [
                    (captions, settings.YT_FIELD_CAPTIONS),
                    (transcript, settings.YT_FIELD_TRANSCRIPT),
                ]:
                    if resource:
                        current_value = get_dict_field(
                            video_resource.metadata, meta_field
                        )
                        new_value = urljoin(
                            "/",
                            resource.file.name.replace(
                                video.website.s3_path, video.website.url_path
                            ),
                        )
                        if current_value != new_value:
                            set_dict_field(
                                video_resource.metadata, meta_field, new_value
                            )
                            video_resource.save()

            if first_transcript_download and len(videos_missing_captions(website)) == 0:
                mail_transcripts_complete_notification(website)


@app.task(acks_late=True)
@single_task(
    timeout=settings.UPDATE_TAGGED_3PLAY_TRANSCRIPT_FREQUENCY, raise_block=False
)
def update_transcripts_for_updated_videos():
    """Check 3play for transcripts with 'updated' tag and update their transcripts"""
    updated_files_response = threeplay_api.threeplay_updated_media_file_request()
    updated_video_data = updated_files_response.get("data")
    if not updated_video_data:
        return

    for video_response in updated_video_data:
        videofiles = VideoFile.objects.filter(
            destination=DESTINATION_YOUTUBE,
            destination_id=video_response.get("reference_id"),
        )
        videos = {videofile.video for videofile in videofiles}
        for video in videos:
            updated = update_transcripts_for_video(video.id)
            if updated:
                threeplay_api.threeplay_remove_tags(video_response.get("id"))


@app.task(acks_late=True)
@single_task(timeout=settings.UPDATE_MISSING_TRANSCRIPT_FREQUENCY, raise_block=False)
def attempt_to_update_missing_transcripts():
    """Check 3play for transcripts for published videos without transcripts"""
    videos = Video.objects.filter(
        Q(pdf_transcript_file__isnull=True)
        | Q(pdf_transcript_file="")
        | Q(webvtt_transcript_file__isnull=True)
        | Q(webvtt_transcript_file="")
    ).filter(website__publish_date__isnull=False)

    for video in videos:
        if (
            VideoFile.objects.filter(
                destination=DESTINATION_YOUTUBE,
                destination_id__isnull=False,
                video=video,
            ).count()
            > 0
        ):
            update_transcripts_for_video.delay(video.id)


@app.task(acks_late=True)
def update_transcripts_for_website(
    website: Website, **kwargs  # noqa: ARG001
):  # pylint:disable=unused-argument
    """Update transcripts from 3play for every video for a website"""

    for video in website.videos.all():
        update_transcripts_for_video(video.id)


def mail_transcripts_complete_notification(website: Website):
    """Notify collaborators that 3play completed video transcripts"""
    with get_message_sender(VideoTranscriptingCompleteMessage) as sender:
        for collaborator in website.collaborators:
            sender.build_and_send_message(
                collaborator,
                {
                    "site": {
                        "title": website.title,
                        "url": urljoin(
                            settings.SITE_BASE_URL,
                            f"sites/{website.name}",
                        ),
                    },
                },
            )


def copy_gdrive_file(gdrive_file, destination_course):
    """
    Copy a Google Drive file to destination course.
    """
    gdrive_service = get_drive_service()
    file_id = gdrive_file.file_id
    gdrive_file = (
        gdrive_service.files()
        .get(fileId=file_id, fields="id, parents", supportsAllDrives=True)
        .execute()
    )
    new_folder_id = destination_course.gdrive_folder
    original_parent_id = gdrive_file["parents"][0]
    original_parent = (
        gdrive_service.files()
        .get(fileId=original_parent_id, fields="name", supportsAllDrives=True)
        .execute()
    )
    original_parent_name = original_parent.get(
        "name"
    )  # either files_final or videos_final
    gdrive_query = (
        f'parents = "{new_folder_id}" and name = "{original_parent_name}" '
        f'and mimeType = "{DRIVE_MIMETYPE_FOLDER}" and not trashed'
    )
    gdrive_files = list(query_files(query=gdrive_query, fields=DRIVE_FILE_FIELDS))
    new_parent_id = gdrive_files[0].get(
        "id"
    )  # ID of either files_final or videos_final folder
    new_file = (
        gdrive_service.files()
        .copy(
            fileId=file_id,
            body={"parents": [new_parent_id]},
            fields="id, parents",
            supportsAllDrives=True,
        )
        .execute()
    )
    return new_file.get("id")


def update_transcript_and_captions(resource, new_transcript_file, new_captions_file):
    """
    Update the associated transcript and captions files for a resource.
    """
    resource.metadata["video_files"][
        "video_transcript_file"
    ] = f"/{str(new_transcript_file).lstrip('/')}"
    resource.metadata["video_files"][
        "video_captions_file"
    ] = f"/{str(new_captions_file).lstrip('/')}"

    resource.save()


def create_drivefile(gdrive_file, new_resource, destination_course, files_or_videos):
    """
    Create a DriveFile for gdrive_file in the destination course.
    """
    gdrive_service = get_drive_service()
    files_or_videos = (
        DRIVE_FOLDER_FILES_FINAL
        if files_or_videos == "files"
        else DRIVE_FOLDER_VIDEOS_FINAL
    )
    gdrive_dl = get_gdrive_file(gdrive_service, gdrive_file.file_id)
    DriveFile.objects.update_or_create(
        file_id=gdrive_dl.get(DRIVE_FILE_ID),
        defaults={
            "checksum": gdrive_dl.get(DRIVE_FILE_MD5_CHECKSUM),
            "name": get_resource_name(new_resource),
            "mime_type": new_resource.metadata["file_type"],
            "status": DriveFileStatus.COMPLETE,
            "website": destination_course,
            "s3_key": str(new_resource.file).lstrip("/"),
            "resource": new_resource,
            "drive_path": (f"{destination_course.short_id}/{files_or_videos}"),
            "modified_time": gdrive_dl.get(DRIVE_FILE_MODIFIED_TIME),
            "created_time": gdrive_dl.get(DRIVE_FILE_CREATED_TIME),
            "size": gdrive_dl.get(DRIVE_FILE_SIZE),
            "download_link": gdrive_dl.get(DRIVE_FILE_DOWNLOAD_LINK),
            "sync_dt": now_in_utc(),
        },
    )


@app.task(acks_late=True)
def copy_video_resource(source_course_id, destination_course_id, source_resource_id):
    """
    Copy a video resource and associated captions/transcripts (celery task).
    """
    source_course = Website.objects.get(uuid=source_course_id)
    destination_course = Website.objects.get(uuid=destination_course_id)
    source_resource = WebsiteContent.objects.get(text_id=source_resource_id)

    video_transcript_file = source_resource.metadata["video_files"][
        "video_transcript_file"
    ]
    video_captions_file = source_resource.metadata["video_files"]["video_captions_file"]
    new_resource = create_new_content(source_resource, destination_course)
    if video_transcript_file and video_captions_file:
        video_transcript_resource = WebsiteContent.objects.filter(
            file=video_transcript_file
        ).first()
        new_transcript_resource = create_new_content(
            video_transcript_resource, destination_course
        )
        new_transcript_file = new_transcript_resource.file

        video_captions_resource = WebsiteContent.objects.filter(
            file=video_captions_file
        ).first()
        new_captions_resource = create_new_content(
            video_captions_resource, destination_course
        )
        new_captions_file = new_captions_resource.file

        update_transcript_and_captions(
            new_resource, new_transcript_file, new_captions_file
        )
        transcript_gdrive_file = DriveFile.objects.filter(
            s3_key=video_transcript_file.lstrip("/")
        ).first()
        if transcript_gdrive_file:
            new_transcript_gdrive_file = copy_gdrive_file(
                transcript_gdrive_file, destination_course
            )
            create_drivefile(
                new_transcript_gdrive_file,
                new_transcript_resource,
                destination_course,
                "files",
            )
        captions_gdrive_file = DriveFile.objects.filter(
            s3_key=video_captions_file.lstrip("/")
        ).first()
        if captions_gdrive_file:
            new_captions_gdrive_file = copy_gdrive_file(
                captions_gdrive_file, destination_course
            )
            create_drivefile(
                new_captions_gdrive_file,
                new_captions_resource,
                destination_course,
                "files",
            )

    videofile = VideoFile.objects.filter(
        video__website=source_course,
        destination="youtube",
        destination_id=source_resource.metadata.get("youtube_id"),
    ).first()

    if videofile:
        video = videofile.video
        Video.objects.create(
            website_content=new_resource,
            video_id=video.video_id,
            status=video.status,
        )

        gdrive_file = DriveFile.objects.filter(video=video).first()
        if gdrive_file:
            new_gdrive_file = copy_gdrive_file(gdrive_file, destination_course)
            create_drivefile(
                new_gdrive_file, new_resource, destination_course, "videos"
            )
