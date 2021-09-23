"""Video tasks"""
import logging

import boto3
from django.conf import settings
from django.db.models import Q
from googleapiclient.errors import HttpError

from main.celery import app
from main.constants import STATUS_CREATED
from videos import threeplay_api
from videos.constants import DESTINATION_YOUTUBE, VideoFileStatus, YouTubeStatus
from videos.models import Video, VideoFile
from videos.youtube import (
    API_QUOTA_ERROR_MSG,
    YouTubeApi,
    is_youtube_enabled,
    mail_youtube_upload_failure,
    mail_youtube_upload_success,
)
from websites.api import is_ocw_site
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.models import Website
from websites.utils import get_dict_query_field, set_dict_field


log = logging.getLogger()


@app.task
def upload_youtube_videos():
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
    for video_file in yt_queue.all():
        error_msg = None
        try:
            youtube = YouTubeApi()
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
        except:  # pylint: disable=bare-except
            log.exception("Error uploading video to Youtube: %s", video_file.s3_key)
            video_file.status = VideoFileStatus.FAILED
        video_file.save()
        if error_msg:
            mail_youtube_upload_failure(video_file)


@app.task
def update_youtube_statuses():
    """
    Update the status of recently uploaded YouTube videos if complete
    """
    if not is_youtube_enabled():
        return
    youtube = YouTubeApi()
    videos_processing = VideoFile.objects.filter(
        Q(status=VideoFileStatus.UPLOADED) & Q(destination=DESTINATION_YOUTUBE)
    )
    for video_file in videos_processing:
        try:
            video_file.destination_status = youtube.video_status(
                video_file.destination_id
            )
            if video_file.destination_status == YouTubeStatus.PROCESSED:
                video_file.status = VideoFileStatus.COMPLETE
            video_file.save()
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
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
    if not as_filter:
        bucket.delete_objects(Delete={"Objects": [{"Key": key}]})
    else:
        for obj in bucket.objects.filter(Prefix=key):
            obj.delete()


@app.task(acks_late=True)
def update_transcripts_for_video(video_id: int):
    """Update transcripts for a video"""
    video = Video.objects.get(id=video_id)
    if threeplay_api.update_transcripts_for_video(video):
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
                    video.pdf_transcript_file.name,
                )
                set_dict_field(
                    metadata,
                    settings.YT_FIELD_CAPTIONS,
                    video.webvtt_transcript_file.name,
                )
                video_resource.save()


@app.task(acks_late=True)
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
def update_transcripts_for_website(website: Website):
    """Update transcripts from 3play for every video for a website"""

    for video in website.videos.all():
        update_transcripts_for_video(video.id)
