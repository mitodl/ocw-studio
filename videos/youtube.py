""" YouTube API interface"""
import http
import logging
import re
import time
from urllib.parse import urljoin

import boto3
import httplib2
import oauth2client
from django.conf import settings
from django.db.models import Q
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from mitol.mail.api import get_message_sender
from smart_open.s3 import Reader

from videos.messages import YouTubeUploadFailureMessage, YouTubeUploadSuccessMessage
from videos.models import VideoFile
from websites.api import is_ocw_site
from websites.models import Website, WebsiteContent
from websites.utils import get_dict_field


log = logging.getLogger(__name__)

# Quota errors should contain the following
API_QUOTA_ERROR_MSG = "quota"


class YouTubeUploadException(Exception):
    """Custom exception for YouTube uploads"""


def is_youtube_enabled() -> bool:
    """ Returns True if youtube is enabled """
    return (
        settings.YT_ACCESS_TOKEN
        and settings.YT_REFRESH_TOKEN
        and settings.YT_CLIENT_ID
        and settings.YT_CLIENT_SECRET
        and settings.YT_PROJECT_ID
    )


def mail_youtube_upload_failure(video_file: VideoFile):
    """Notify collaborators that a youtube upload failed"""
    with get_message_sender(YouTubeUploadFailureMessage) as sender:
        website = video_file.video.website
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
                    "video": {"filename": video_file.video.source_key.split("/")[-1]},
                },
            )


def mail_youtube_upload_success(video_file: VideoFile):
    """Notify collaborators that a youtube upload succeeded"""
    with get_message_sender(YouTubeUploadSuccessMessage) as sender:
        website = video_file.video.website
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
                    "video": {
                        "filename": video_file.video.source_key.split("/")[-1],
                        "url": f"https://www.youtube.com/watch?v={video_file.destination_id}",
                    },
                },
            )


def resumable_upload(request, max_retries=10):
    """
    Upload a video to YouTube and resume on failure up to 10 times, adapted from YouTube API example.
    To use resumable media you must use a MediaFileUpload object and flag it as a resumable upload.
    You then repeatedly call next_chunk() on the googleapiclient.http.HttpRequest object until the
    upload is complete.

    Args:
        request(googleapiclient.http.HttpRequest): The Youtube API execute request to process
        max_retries(int): Maximum # of times to retry an upload (default 10)

    Returns:
        dict: The YouTube API response
    """
    response = None
    error = None

    retry = 0
    retry_exceptions = (OSError, http.client.HTTPException)
    retry_statuses = [500, 502, 503, 504]

    while response is None:
        try:
            _, response = request.next_chunk()
            if response is not None and "id" not in response:
                raise YouTubeUploadException("YouTube upload failed: %s" % response)
        except HttpError as e:
            if e.resp.status in retry_statuses:
                error = e
            else:
                raise
        except retry_exceptions as e:
            error = e

        if error is not None:
            retry += 1
            if retry > max_retries:
                log.error("Final upload failure")
                raise YouTubeUploadException(
                    "Retried YouTube upload 10x, giving up"
                ) from error
            sleep_time = 2 ** retry
            time.sleep(sleep_time)

    return response


def strip_bad_chars(txt):
    """
    Remove any characters forbidden by Youtube (<, >) from text

    Args:
        txt(str): Text to remove characters from.

    Returns:
        str: Text without bad characters
    """
    return re.sub("<|>", "", txt)


class YouTubeApi:
    """
    Class interface to YouTube API calls
    """

    client = None
    s3 = None

    def __init__(self):
        """
        Generate an authorized YouTube API client and S3 client
        """
        credentials = oauth2client.client.GoogleCredentials(
            settings.YT_ACCESS_TOKEN,
            settings.YT_CLIENT_ID,
            settings.YT_CLIENT_SECRET,
            settings.YT_REFRESH_TOKEN,
            None,
            "https://accounts.google.com/o/oauth2/token",
            None,
        )
        authorization = credentials.authorize(httplib2.Http())
        credentials.refresh(authorization)
        self.client = build("youtube", "v3", credentials=credentials)
        self.s3 = boto3.client("s3")

    def video_status(self, video_id):
        """
        Checks the  status of a video. 'processed' = ready for viewing.

        Args:
            video_id(str): YouTube video id

        Returns:
            str: status of the YouTube video

        """
        results = self.client.videos().list(part="status", id=video_id).execute()
        return results["items"][0]["status"]["uploadStatus"]

    def upload_video(self, videofile: VideoFile, privacy="unlisted"):
        """
        Transfer the video's original video file from S3 to YouTube.
        The YT account must be validated for videos > 15 minutes long:
        https://www.youtube.com/verify

        Args:
            video(Video): The Video object whose original source file will be uploaded'
            privacy(str): The privacy level to set the YouTube video to.

        Returns:
            dict: YouTube API response

        """
        original_name = videofile.video.source_key.split("/")[-1]
        request_body = dict(
            snippet=dict(
                title=strip_bad_chars(original_name)[:100],
                description="",
                categoryId=settings.YT_CATEGORY_ID,
            ),
            status=dict(privacyStatus=privacy),
        )

        with Reader(settings.AWS_STORAGE_BUCKET_NAME, videofile.s3_key) as s3_stream:
            request = self.client.videos().insert(
                part=",".join(request_body.keys()),
                body=request_body,
                media_body=MediaIoBaseUpload(
                    s3_stream, mimetype="video/*", chunksize=-1, resumable=True
                ),
            )

        response = resumable_upload(request)
        return response

    def update_privacy(self, youtube_id: str, privacy: str):
        """Update the privacy level of a video"""
        response = (
            self.client.videos()
            .update(part="status", body={"id": youtube_id, "privacyStatus": privacy})
            .execute()
        )
        log.error(response)

    def update_video(self, resource: WebsiteContent, privacy=None):
        """
        Update a video's metadata based on a WebsiteContent object that is assumed to have certain fields.
        """
        metadata = resource.metadata
        description = get_dict_field(metadata, settings.YT_FIELD_DESCRIPTION)
        speakers = get_dict_field(metadata, settings.YT_FIELD_SPEAKERS)
        if speakers:
            description = f"{description}\n\nSpeakers: {speakers}"
        youtube_id = get_dict_field(metadata, settings.YT_FIELD_ID)
        self.client.videos().update(
            part="snippet",
            body={
                "id": youtube_id,
                "snippet": {
                    "title": resource.title,
                    "description": description,
                    "tags": get_dict_field(metadata, settings.YT_FIELD_TAGS),
                    "categoryId": settings.YT_CATEGORY_ID,
                },
            },
        ).execute()
        if privacy:
            self.update_privacy(youtube_id, privacy=privacy)

    def delete_video(self, video_id):
        """
        Delete a video from YouTube

        Args:
            video_id(str): YouTube video id

        Returns:
            int: 204 status code if successful
        """
        return self.client.videos().delete(id=video_id).execute()


def update_youtube_metadata(website: Website, privacy=None):
    """ Update YouTube video metadata via the API """
    if not is_youtube_enabled() or not is_ocw_site(website):
        return
    youtube = YouTubeApi()
    query_id_field = f"metadata__{'__'.join(settings.YT_FIELD_ID.split('.'))}"
    for video_resource in website.websitecontent_set.filter(
        Q(metadata__filetype="Video")
    ).exclude(Q(**{query_id_field: None}) | Q(**{query_id_field: ""})):
        youtube.update_video(video_resource, privacy=privacy)
