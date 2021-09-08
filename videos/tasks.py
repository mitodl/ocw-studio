"""Video tasks"""
import logging

import boto3
from django.conf import settings
from django.db.models import Q
from googleapiclient.errors import HttpError

from main.celery import app
from main.constants import STATUS_CREATED
from videos.constants import DESTINATION_YOUTUBE, VideoFileStatus, YouTubeStatus
from videos.models import VideoFile
from videos.youtube import (
    API_QUOTA_ERROR_MSG,
    YouTubeApi,
    mail_youtube_upload_failure,
    mail_youtube_upload_success,
)


log = logging.getLogger()


def is_youtube_enabled() -> bool:
    """ Returns True if youtube is enabled """
    return (
        settings.YT_ACCESS_TOKEN
        and settings.YT_REFRESH_TOKEN
        and settings.YT_CLIENT_ID
        and settings.YT_CLIENT_SECRET
        and settings.YT_PROJECT_ID
    )


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
