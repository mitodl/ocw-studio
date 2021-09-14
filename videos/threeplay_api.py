"""3play api requests"""
import logging
from io import BytesIO

import requests
from django.conf import settings
from django.core.files import File

from videos.constants import DESTINATION_YOUTUBE
from videos.models import Video


log = logging.getLogger(__name__)


def threeplay_updated_media_file_request() -> dict:
    """3play data request to get files with 'updated' tag"""
    payload = {"label": "updated", "api_key": settings.THREEPLAY_API_KEY}
    url = "https://api.3playmedia.com/v3/files"
    response = requests.get(url, payload)
    if response:
        return response.json()
    else:
        return {}


def threeplay_remove_tags(threeplay_video_id: int):
    """3play patch to remove tag from video file"""
    payload = {"label": "", "api_key": settings.THREEPLAY_API_KEY}
    url = f"https://api.3playmedia.com/v3/files/{threeplay_video_id}"
    requests.patch(url, payload)


def threeplay_transcript_api_request(youtube_id: str) -> dict:
    """3play data requst to get transcripts by youtube_id"""
    payload = {
        "media_file_reference_id": youtube_id,
        "api_key": settings.THREEPLAY_API_KEY,
    }
    url = "https://api.3playmedia.com/v3/transcripts"
    response = requests.get(url, payload)
    if response:
        return response.json()
    else:
        return {}


def fetch_file(source_url: str) -> BytesIO:
    """Fetch transcript file from 3play site"""

    response = requests.get(source_url)

    if (
        response.status_code != 200
        or response.content
        == b'{"is_error":true,"error_description":"record not found"}'
    ):
        log.error(
            "Could not open 3play transcript at %s",
            source_url,
        )
        return False

    file = BytesIO()
    file.write(response.content)
    return file


def update_transcripts_for_video(video: Video) -> bool:
    """Download transcripts from 3play, upload them to s3 and update the Video file"""

    youtube_video_file = video.videofiles.filter(
        destination=DESTINATION_YOUTUBE
    ).first()

    if not (youtube_video_file and youtube_video_file.destination_id):
        return False
    else:
        youtube_id = youtube_video_file.destination_id

    threeplay_transcript_json = threeplay_transcript_api_request(youtube_id)

    if (
        threeplay_transcript_json.get("data")
        and len(threeplay_transcript_json.get("data")) > 0
    ):
        transcript_id = threeplay_transcript_json["data"][0].get("id")
        media_file_id = threeplay_transcript_json["data"][0].get("media_file_id")

        transcript_url_base = (
            f"https://static.3playmedia.com/p/files/{media_file_id}/threeplay_transcripts/"
            f"{transcript_id}?project_id={settings.THREEPLAY_PROJECT_ID}"
        )

        pdf_url = transcript_url_base + "&format_id=46"
        pdf_response = fetch_file(pdf_url)
        if pdf_response:
            video.pdf_transcript_file.save(
                "transcript.pdf", File(pdf_response, name="transcript.pdf")
            )

        webvtt_url = transcript_url_base + "&format_id=51"
        webvtt_response = fetch_file(webvtt_url)
        if webvtt_response:
            video.webvtt_transcript_file.save(
                "transcript_webvtt", File(webvtt_response, name="transcript_webvtt")
            )

        video.save()
        return True

    return False
