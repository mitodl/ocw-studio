"""Management command to delete duplicate captions from YouTube videos"""

import logging
from io import BytesIO

from django.core.management.base import CommandError
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from main.management.commands.filter import WebsiteFilterCommand
from videos.constants import DESTINATION_YOUTUBE
from videos.models import VideoFile
from videos.youtube import CAPTION_UPLOAD_NAME, YouTubeApi
from websites.models import Website

log = logging.getLogger(__name__)
LEGACY_CAPTIONS_NAME = "ocw_studio_upload"
ERROR_NO_WEBSITES = "No matching websites found."


class Command(WebsiteFilterCommand):
    """
    Checks if the most recently updated captions track is 'CC (English)'.
    If it's 'ocw_studio_upload', copy into 'CC (English)' and remove the
    'ocw_studio_upload' track.
    If it's 'CC (English)' and there is a track named 'ocw_studio_upload',
    remove the 'ocw_studio_upload' track.
    """

    help = __doc__

    def handle(self, *args, **options):
        """
        Handle the deletion of duplicate captions from YouTube videos.
        """
        super().handle(*args, **options)

        all_websites = Website.objects.all()

        filtered_websites = self.filter_websites(websites=all_websites)

        if not filtered_websites.exists():
            raise CommandError(ERROR_NO_WEBSITES)

        video_files = VideoFile.objects.filter(
            destination=DESTINATION_YOUTUBE,
            destination_id__isnull=False,
            video__website__in=filtered_websites,
        ).select_related("video", "video__website")

        youtube = YouTubeApi()

        for vf in video_files:
            video_id = vf.destination_id
            try:
                captions_response = (
                    youtube.client.captions()
                    .list(part="snippet", videoId=video_id)
                    .execute()
                )
                items = captions_response.get("items", [])
                items.sort(
                    key=lambda captions: captions["snippet"].get("lastUpdated", ""),
                    reverse=True,
                )
                if not items:
                    continue

                newest = items[0]
                newest_name = newest["snippet"]["name"]

                legacy_tracks = [
                    captions
                    for captions in items
                    if captions["snippet"]["name"] == LEGACY_CAPTIONS_NAME
                ]

                if newest_name == LEGACY_CAPTIONS_NAME:
                    caption_id = newest["id"]
                    caption_content = (
                        youtube.client.captions().download(id=caption_id).execute()
                    )

                    media_body = MediaIoBaseUpload(
                        BytesIO(caption_content),
                        mimetype="text/vtt",
                        chunksize=-1,
                        resumable=True,
                    )
                    cc_english = [
                        captions
                        for captions in items
                        if captions["snippet"]["name"] == CAPTION_UPLOAD_NAME
                    ]
                    if cc_english:
                        youtube.client.captions().update(
                            part="snippet",
                            body={"id": cc_english[0]["id"]},
                            media_body=media_body,
                        ).execute()
                    else:
                        youtube.client.captions().insert(
                            part="snippet",
                            sync=False,
                            body={
                                "snippet": {
                                    "language": "en",
                                    "name": CAPTION_UPLOAD_NAME,
                                    "videoId": video_id,
                                }
                            },
                            media_body=media_body,
                        ).execute()

                    youtube.client.captions().delete(id=caption_id).execute()

                elif newest_name == CAPTION_UPLOAD_NAME and legacy_tracks:
                    for track in legacy_tracks:
                        youtube.client.captions().delete(id=track["id"]).execute()

            except HttpError:
                log.exception("Error processing video %s", video_id)
