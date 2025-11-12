"""YouTube API interface"""

import http
import logging
import re
import time
from collections import Counter
from io import BytesIO
from typing import Literal
from urllib.parse import urljoin

from django.conf import settings
from django.db.models import Q
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from mitol.mail.api import get_message_sender
from smart_open.s3 import Reader

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from main.s3_utils import get_boto3_client
from main.utils import truncate_words
from videos.constants import (
    DESTINATION_YOUTUBE,
    YT_MAX_LENGTH_DESCRIPTION,
    YT_MAX_LENGTH_TITLE,
)
from videos.messages import YouTubeUploadFailureMessage, YouTubeUploadSuccessMessage
from videos.models import VideoFile
from videos.utils import get_course_tag, get_tags_with_course, parse_tags
from websites.api import is_ocw_site
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.models import Website, WebsiteContent
from websites.utils import get_dict_field, get_dict_query_field

log = logging.getLogger(__name__)

# Quota errors should contain the following
API_QUOTA_ERROR_MSG = "quota"
CAPTION_UPLOAD_NAME = "CC (English)"


class YouTubeUploadException(Exception):  # noqa: N818
    """Custom exception for YouTube uploads"""


def is_youtube_enabled() -> bool:
    """Returns True if youtube is enabled"""  # noqa: D401
    return (
        settings.YT_ACCESS_TOKEN
        and settings.YT_REFRESH_TOKEN
        and settings.YT_CLIENT_ID
        and settings.YT_CLIENT_SECRET
        and settings.YT_PROJECT_ID
    )


def mail_youtube_upload_failure(video_file: VideoFile):
    """Notify collaborators that a youtube upload failed"""
    try:
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
                        "video": {
                            "filename": video_file.video.source_key.split("/")[-1]
                        },
                    },
                )
    except Exception:
        log.exception("Failed to send YouTube upload failure notification")


def mail_youtube_upload_success(video_file: VideoFile):
    """Notify collaborators that a youtube upload succeeded"""
    try:
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
    except Exception:
        log.exception("Failed to send YouTube upload success notification")


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
    """  # noqa: E501
    response = None
    error = None

    retry = 0
    retry_exceptions = (OSError, http.client.HTTPException)
    retry_statuses = [500, 502, 503, 504]

    while response is None:
        try:
            _, response = request.next_chunk()
            if response is not None and "id" not in response:
                msg = f"YouTube upload failed: {response}"
                raise YouTubeUploadException(msg)
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
                msg = "Retried YouTube upload 10x, giving up"
                raise YouTubeUploadException(msg) from error
            sleep_time = 2**retry
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
        credentials = Credentials(
            settings.YT_ACCESS_TOKEN,
            token_uri="https://accounts.google.com/o/oauth2/token",  # noqa: S106
            client_id=settings.YT_CLIENT_ID,
            client_secret=settings.YT_CLIENT_SECRET,
            refresh_token=settings.YT_REFRESH_TOKEN,
        )
        self.client = build("youtube", "v3", credentials=credentials)
        self.s3 = get_boto3_client("s3")

    def video_status(self, video_id):
        """
        Checks the  status of a video. 'processed' = ready for viewing.

        Args:
            video_id(str): YouTube video id

        Returns:
            str: status of the YouTube video

        """  # noqa: D401
        results = self.client.videos().list(part="status", id=video_id).execute()
        return results["items"][0]["status"]["uploadStatus"]

    def upload_video(
        self,
        videofile: VideoFile,
        privacy="unlisted",
        notify_subscribers=False,  # noqa: FBT002
        existing_tags="",
    ):
        """
        Transfer the video's original video file from S3 to YouTube.
        The YT account must be validated for videos > 15 minutes long:
        https://www.youtube.com/verify

        Args:
            video(Video): The Video object whose original source file will be uploaded
            privacy(str): The privacy level to set the YouTube video to.
            notify_subscribers(bool): whether subscribers should be notified
            existing_tags(str): Existing comma-separated tags from
                WebsiteContent metadata

        Returns:
            tuple: (YouTube API response dict, merged tags string)

        """
        original_name = videofile.video.source_key.split("/")[-1]
        request_body = {
            "snippet": {
                "title": truncate_words(
                    strip_bad_chars(original_name), YT_MAX_LENGTH_TITLE
                ),
                "description": "",
                "categoryId": settings.YT_CATEGORY_ID,
            },
            "status": {"privacyStatus": privacy},
        }

        merged_tags = None
        if course_slug := get_course_tag(videofile.video.website):
            # Merge existing tags with course tag
            merged_tags = (
                f"{existing_tags}, {course_slug}" if existing_tags else course_slug
            )
            request_body["snippet"]["tags"] = merged_tags

        with Reader(settings.AWS_STORAGE_BUCKET_NAME, videofile.s3_key) as s3_stream:
            request = self.client.videos().insert(
                part=",".join(request_body.keys()),
                body=request_body,
                notifySubscribers=notify_subscribers,
                media_body=MediaIoBaseUpload(
                    s3_stream, mimetype="video/*", chunksize=-1, resumable=True
                ),
            )

        return resumable_upload(request), merged_tags

    def update_privacy(self, youtube_id: str, privacy: str):
        """Update the privacy level of a video"""
        self.client.videos().update(
            part="status",
            body={
                "id": youtube_id,
                "status": {"privacyStatus": privacy, "embeddable": True},
            },
        ).execute()

    def update_captions(self, resource: WebsiteContent, youtube_id: str):
        """Update captions for video"""

        videofile = VideoFile.objects.filter(
            destination=DESTINATION_YOUTUBE,
            destination_id=youtube_id,
            video__website=resource.website,
        ).last()

        if not videofile or not videofile.video.webvtt_transcript_file:
            return

        content = videofile.video.webvtt_transcript_file.open(mode="rb").read()

        media_body = MediaIoBaseUpload(
            BytesIO(content), mimetype="text/vtt", chunksize=-1, resumable=True
        )

        existing_captions = (
            self.client.captions().list(part="snippet", videoId=youtube_id).execute()
        )

        existing_captions = existing_captions.get("items", [])
        existing_captions = list(
            filter(
                lambda caption_file: caption_file.get("snippet", {}).get("name")
                == CAPTION_UPLOAD_NAME,
                existing_captions,
            )
        )

        if existing_captions:
            self.client.captions().update(
                part="snippet",
                body={"id": existing_captions[0].get("id")},
                media_body=media_body,
            ).execute()
        else:
            self.client.captions().insert(
                part="snippet",
                sync=False,
                body={
                    "snippet": {
                        "language": "en",
                        "name": CAPTION_UPLOAD_NAME,
                        "videoId": youtube_id,
                    }
                },
                media_body=media_body,
            ).execute()

    def update_video(self, resource: WebsiteContent, privacy=None):
        """
        Update a video's metadata based on a WebsiteContent object that is assumed to have certain fields.
        """  # noqa: E501
        metadata = resource.metadata
        description = get_dict_field(metadata, settings.YT_FIELD_DESCRIPTION)
        speakers = get_dict_field(metadata, settings.YT_FIELD_SPEAKERS)
        if speakers:
            description = f"{description}\n\nSpeakers: {speakers}"
        youtube_id = get_dict_field(metadata, settings.YT_FIELD_ID)
        course_slug = get_course_tag(resource.website)
        self.client.videos().update(
            part="snippet",
            body={
                "id": youtube_id,
                "snippet": {
                    "title": truncate_words(
                        strip_bad_chars(resource.title), YT_MAX_LENGTH_TITLE
                    ),
                    "description": truncate_words(
                        strip_bad_chars(description), YT_MAX_LENGTH_DESCRIPTION
                    ),
                    "tags": parse_tags(get_tags_with_course(metadata, course_slug)),
                    "categoryId": settings.YT_CATEGORY_ID,
                },
            },
        ).execute()

        self.update_captions(resource, youtube_id)

        if privacy:
            self.update_privacy(youtube_id, privacy=privacy)

    def update_video_tags(self, youtube_id: str, tags: str):
        """
        Update only the tags for a YouTube video.

        Args:
            youtube_id (str): The YouTube video ID
            tags (str): Comma-separated tags string

        Returns:
            dict: YouTube API response
        """
        # Get current video snippet to preserve other fields
        video_response = (
            self.client.videos().list(part="snippet", id=youtube_id).execute()
        )

        if not video_response.get("items"):
            msg = f"Video {youtube_id} not found"
            raise YouTubeUploadException(msg)

        current_snippet = video_response["items"][0]["snippet"]

        # Update only the tags field
        current_snippet["tags"] = parse_tags(tags)

        # Update the video with modified snippet
        return (
            self.client.videos()
            .update(
                part="snippet",
                body={
                    "id": youtube_id,
                    "snippet": current_snippet,
                },
            )
            .execute()
        )

    @classmethod
    def get_all_video_captions(
        cls,
        website_ids: list[str] | None = None,
        video_ids: list[int] | None = None,
        youtube_ids: list[str] | None = None,
        *,
        only_dups: bool = False,
    ) -> list[dict]:
        """
        Get caption tracks for all YouTube videos in database, with optional filtering
        and duplicate detection.

        Args:
            website_ids (list[str], optional): Filter videos by website short_ids
            video_ids (list[int], optional): Filter videos by video IDs
            youtube_ids (list[str], optional): Filter videos by YouTube IDs
            only_dups (bool, optional): Only return videos with duplicate captions
                in any language. Defaults to False.

        Returns:
            list[dict]: List of dicts containing video info and caption tracks
        """
        youtube = cls()
        video_captions = []

        video_files = VideoFile.objects.filter(
            destination=DESTINATION_YOUTUBE, destination_id__isnull=False
        ).select_related("video", "video__website")

        if website_ids:
            video_files = video_files.filter(video__website__short_id__in=website_ids)
        if video_ids:
            video_files = video_files.filter(video_id__in=video_ids)
        if youtube_ids:
            video_files = video_files.filter(destination_id__in=youtube_ids)

        for video_file in video_files:
            try:
                captions_response = (
                    youtube.client.captions()
                    .list(part="snippet", videoId=video_file.destination_id)
                    .execute()
                )

                video_info = {
                    "video_id": video_file.destination_id,
                    "filename": video_file.video.source_key.split("/")[-1],
                    "website": video_file.video.website.name,
                    "captions": [],
                }

                language_counter = Counter()
                for caption in captions_response.get("items", []):
                    caption_info = {
                        "id": caption["id"],
                        "language": caption["snippet"]["language"],
                        "name": caption["snippet"].get("name", ""),
                        "last_updated": caption["snippet"].get("lastUpdated", ""),
                    }
                    language_counter[caption_info["language"]] += 1
                    video_info["captions"].append(caption_info)

                video_info["language_counts"] = dict(language_counter)
                has_duplicates = any(count > 1 for count in language_counter.values())
                if not only_dups or has_duplicates:
                    video_captions.append(video_info)

            except HttpError:
                log.exception(
                    "Failed to get captions for video %s", video_file.destination_id
                )
                continue

        return video_captions


def get_video_privacy_status(
    *, version, is_draft, previously_published
) -> Literal["public", "unlisted"] | None:
    """
    Determine the appropriate YouTube privacy status for a video.

    Args:
        version: The version being published (VERSION_LIVE or VERSION_DRAFT)
        is_draft: Whether the video is marked as draft content
        previously_published: Whether the site has been published before
        and not unpublished

    Returns:
        "public", "unlisted", or None (to maintain current privacy)
    """
    if version == VERSION_LIVE and not is_draft:
        return "public"
    elif not previously_published or is_draft:
        return "unlisted"
    else:
        return None


def update_youtube_metadata(website: Website, version=VERSION_DRAFT) -> None:
    """Update YouTube video metadata via the API"""
    if not is_youtube_enabled() or not is_ocw_site(website):
        return
    query_id_field = get_dict_query_field("metadata", settings.YT_FIELD_ID)
    video_resources = website.websitecontent_set.filter(
        Q(metadata__resourcetype=RESOURCE_TYPE_VIDEO)
    ).exclude(Q(**{query_id_field: None}) | Q(**{query_id_field: ""}))
    if video_resources.count() == 0:
        return
    previously_published: bool = (
        website.publish_date is not None and not website.unpublished
    )
    youtube: YouTubeApi = YouTubeApi()
    for video_resource in video_resources:
        is_draft = get_dict_field(video_resource.metadata, "draft") is True
        youtube_id = get_dict_field(video_resource.metadata, settings.YT_FIELD_ID)
        # do not run this for any old imported videos
        if VideoFile.objects.filter(
            video__website=website, destination_id=youtube_id
        ).exists():
            try:
                privacy = get_video_privacy_status(
                    version=version,
                    is_draft=is_draft,
                    previously_published=previously_published,
                )
                youtube.update_video(video_resource, privacy=privacy)
            except:  # pylint:disable=bare-except  # noqa: E722
                log.exception(
                    "Unexpected error updating metadata for video resource %d",
                    video_resource.id,
                )
