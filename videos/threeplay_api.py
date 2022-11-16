"""3play api requests"""
import logging
from io import BytesIO
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.files import File

from videos.constants import DESTINATION_YOUTUBE
from videos.models import Video


log = logging.getLogger(__name__)


def get_folder(name: str) -> dict:
    """3play data request to get folders by name"""
    payload = {"name": name, "api_key": settings.THREEPLAY_API_KEY}
    url = "https://api.3playmedia.com/v3/batches/"
    response = requests.get(url, payload)
    if response:
        return response.json()
    else:
        return {}


def create_folder(name: str) -> dict:
    """3play data request to create folder"""
    payload = {"name": name, "api_key": settings.THREEPLAY_API_KEY}
    url = "https://api.3playmedia.com/v3/batches/"
    response = requests.post(url, payload)
    if response:
        return response.json()
    else:
        return {}


def get_or_create_folder(name: str) -> int:
    """3play data request to either get or create a folder by name"""

    folder_response = get_folder(name)
    if folder_response.get("data") and len(folder_response.get("data")) > 0:
        folder_id = folder_response.get("data")[0].get("id")
    else:
        folder_response = create_folder(name)
        folder_id = folder_response.get("data").get("id")

    return folder_id


def threeplay_updated_media_file_request() -> dict:
    """3play data request to get files with 'updated' tag"""
    payload = {"label": "updated", "api_key": settings.THREEPLAY_API_KEY}
    url = "https://api.3playmedia.com/v3/files"
    response = requests.get(url, payload)
    if response:
        return response.json()
    else:
        return {}


def threeplay_upload_video_request(
    folder_name: str, youtube_id: str, title: str
) -> dict:
    """3play data request to upload a video from youtube"""
    youtube_url = "https://www.youtube.com/watch?v=" + youtube_id
    folder_id = get_or_create_folder(folder_name)

    payload = {
        "source_url": youtube_url,
        "reference_id": youtube_id,
        "api_key": settings.THREEPLAY_API_KEY,
        "language_id": [1],
        "name": title,
        "batch_id": folder_id,
    }
    url = "https://api.3playmedia.com/v3/files/"
    response = requests.post(url, payload)
    if response:
        return response.json()
    else:
        return {}


def threeplay_order_transcript_request(video_id: int, threeplay_video_id: int) -> dict:
    """3play request to order a transcript"""

    payload = {
        "turnaround_level_id": 5,
        "media_file_id": threeplay_video_id,
        "api_key": settings.THREEPLAY_API_KEY,
    }
    url = "https://api.3playmedia.com/v3/transcripts/order/transcription"

    if settings.THREEPLAY_CALLBACK_KEY:
        callback_url = urljoin(
            settings.SITE_BASE_URL,
            f"api/transcription-jobs/?video_id={str(video_id)}&callback_key={settings.THREEPLAY_CALLBACK_KEY}",
        )

        payload["callback"] = callback_url

    response = requests.post(url, payload)
    if response:
        return response.json()
    else:
        raise Exception("3Play transcript request failed for video_id " + str(video_id))


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
        and threeplay_transcript_json.get("data")[0].get("status") == "complete"
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
                "transcript.webvtt", File(webvtt_response, name="transcript.webvtt")
            )

        video.save()
        return True

    return False
