"""
Management command to standardize caption tracks for YouTube videos by
consolidating 'ocw_captions_upload' tracks into 'CC (English)' and removing duplicates.
"""

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
LEGACY_CAPTIONS_NAME = "ocw_captions_upload"
ERROR_NO_WEBSITES = "No matching websites found."


class Command(WebsiteFilterCommand):
    """
    Checks if the most recently updated captions track is 'CC (English)'.
    If it's 'ocw_captions_upload', copy into 'CC (English)' and remove the
    'ocw_captions_upload' track.
    If it's 'CC (English)' and there is a track named 'ocw_captions_upload',
    remove the 'ocw_captions_upload' track.
    All other captions tracks, including auto-generated captions, are ignored.
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

        for video_file in video_files:
            video_id = video_file.destination_id
            try:
                captions_response = (
                    youtube.client.captions()
                    .list(part="snippet", videoId=video_id)
                    .execute()
                )
                items = captions_response.get("items", [])
                if not items:
                    continue

                legacy_tracks = [
                    captions
                    for captions in items
                    if captions["snippet"]["name"] == LEGACY_CAPTIONS_NAME
                ]
                cc_english_tracks = [
                    captions
                    for captions in items
                    if captions["snippet"]["name"] == CAPTION_UPLOAD_NAME
                ]

                if legacy_tracks:
                    legacy_track = max(
                        legacy_tracks,
                        key=lambda captions: captions["snippet"].get("lastUpdated", ""),
                    )

                    legacy_newer = True
                    if cc_english_tracks:
                        cc_track = max(
                            cc_english_tracks,
                            key=lambda captions: captions["snippet"].get(
                                "lastUpdated", ""
                            ),
                        )
                        legacy_newer = legacy_track["snippet"].get(
                            "lastUpdated", ""
                        ) > cc_track["snippet"].get("lastUpdated", "")

                    if legacy_newer:
                        caption_id = legacy_track["id"]
                        caption_content = (
                            youtube.client.captions().download(id=caption_id).execute()
                        )

                        media_body = MediaIoBaseUpload(
                            BytesIO(caption_content),
                            mimetype="text/vtt",
                            chunksize=-1,
                            resumable=True,
                        )

                        if cc_english_tracks:
                            youtube.client.captions().update(
                                part="snippet",
                                body={"id": cc_english_tracks[0]["id"]},
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

                    for track in legacy_tracks:
                        youtube.client.captions().delete(id=track["id"]).execute()

            except HttpError:
                log.exception("Error processing video %s", video_id)
