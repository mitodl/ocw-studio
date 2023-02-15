"""Video tasks"""
import logging
from urllib.parse import urljoin

import celery
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from googleapiclient.errors import HttpError
from mitol.mail.api import get_message_sender

from content_sync.decorators import single_task
from gdrive_sync.models import DriveFile
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
from websites.utils import get_dict_query_field, set_dict_field


log = logging.getLogger()


@app.task(bind=True)
@single_task(timeout=settings.YT_UPLOAD_FREQUENCY, raise_block=False)
def upload_youtube_videos(self):
    """
    Upload public videos one at a time to YouTube (if not already there) until the daily maximum is reached.
    """
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
    group_tasks = []

    for video_file in yt_queue:
        error_msg = None
        try:
            response = youtube.upload_video(video_file)
            video_file.destination_id = response["id"]
            video_file.destination_status = response["status"]["uploadStatus"]
            video_file.status = VideoFileStatus.UPLOADED
            group_tasks.append(start_transcript_job.s(video_file.video.id))
        except HttpError as error:
            error_msg = error.content.decode("utf-8")
            if API_QUOTA_ERROR_MSG in error_msg:
                break
            log.exception("HttpError uploading video to Youtube: %s", video_file.s3_key)
            video_file.status = VideoFileStatus.FAILED
        except:  # pylint: disable=bare-except
            log.exception("Error uploading video to Youtube: %s", video_file.s3_key)
            video_file.status = VideoFileStatus.FAILED
        video_file.save()
        if error_msg:
            mail_youtube_upload_failure(video_file)

    if group_tasks:
        raise self.replace(celery.group(group_tasks))


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

    if video_resource:
        title = video_resource.title
        video_filename = video_resource.filename
    else:
        title = video.source_key.split("/")[-1]
        video_filename = title

    captions = WebsiteContent.objects.filter(
        Q(website=video.website) & Q(filename=f"{video_filename}_captions")
    ).first()

    transcript = WebsiteContent.objects.filter(
        Q(website=video.website) & Q(filename=f"{video_filename}_transcript")
    ).first()

    if captions or transcript:  # check for existing captions or transcript
        if captions:
            video.metadata["video_files"]["video_captions_file"] = str(captions.file)
        if transcript:
            video.metadata["video_files"]["video_transcript_file"] = str(
                transcript.file
            )
        video.save()

    else:  # if none, request a transcript through the 3Play API
        response = threeplay_api.threeplay_upload_video_request(
            folder_name, youtube_id, title
        )

        threeplay_file_id = response.get("data").get("id")

        if threeplay_file_id:
            threeplay_api.threeplay_order_transcript_request(
                video.id, threeplay_file_id
            )
            video.status = VideoStatus.SUBMITTED_FOR_TRANSCRIPTION
            video.save()


@app.task
@single_task(timeout=settings.YT_STATUS_UPDATE_FREQUENCY, raise_block=False)
def update_youtube_statuses():
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
            mail_youtube_upload_success(video_file)
        except IndexError:
            # Video might be a dupe or deleted, mark it as failed and continue to next one.
            video_file.status = VideoFileStatus.FAILED
            video_file.save()
            log.exception(
                "Status of YouTube video not found: youtube_id %s",
                video_file.destination_id,
            )
            mail_youtube_upload_failure(video_file)
        except HttpError as error:
            if API_QUOTA_ERROR_MSG in error.content.decode("utf-8"):
                # Don't raise the error, task will try on next run until daily quota is reset
                break
            log.exception(
                "Error for youtube_id %s: %s",
                video_file.destination_id,
                error.content.decode("utf-8"),
            )
            mail_youtube_upload_failure(video_file)


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
        if error.resp.status == 404:
            log.info("Not found on Youtube, already deleted?", video_id=video_id)
        else:
            raise


@app.task(acks_late=True)
def delete_s3_objects(
    key: str, as_filter: bool = False
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
def update_transcripts_for_video(video_id: int):
    """Update transcripts for a video"""
    video = Video.objects.get(id=video_id)
    if threeplay_api.update_transcripts_for_video(video):
        first_transcript_download = False

        if video.status != VideoStatus.COMPLETE:
            video.status = VideoStatus.COMPLETE
            video.save()
            first_transcript_download = True

        website = video.website
        if is_ocw_site(website):
            search_fields = {}
            search_fields[
                get_dict_query_field("metadata", settings.FIELD_RESOURCETYPE)
            ] = RESOURCE_TYPE_VIDEO
            search_fields[
                get_dict_query_field("metadata", settings.YT_FIELD_ID)
            ] = video.youtube_id()

            for video_resource in website.websitecontent_set.filter(**search_fields):
                metadata = video_resource.metadata
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

                if (
                    first_transcript_download
                    and len(videos_missing_captions(website)) == 0
                ):
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
    website: Website, **kwargs
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
