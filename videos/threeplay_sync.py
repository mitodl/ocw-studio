import logging
from collections.abc import Callable
from uuid import uuid4

from django.conf import settings
from django.core.files import File

from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename, get_file_extension
from videos.constants import PDF_FORMAT_ID, WEBVTT_FORMAT_ID
from videos.threeplay_api import fetch_file, threeplay_transcript_api_request
from videos.utils import generate_s3_path, get_content_dirpath
from websites.models import WebsiteContent

log = logging.getLogger()

transcript_base_url = (
    "https://static.3playmedia.com/p/files/{media_file_id}/threeplay_transcripts/"
    "{transcript_id}?project_id={project_id}"
)

extension_map = {
    "vtt": {
        "ext": "captions",
        "file_type": "application/x-subrip",
        "resource_type": "Other",
    },
    "webvtt": {
        "ext": "captions",
        "file_type": "application/x-subrip",
        "resource_type": "Other",
    },
    "pdf": {
        "ext": "transcript",
        "file_type": "application/pdf",
        "resource_type": "Document",
    },
}


def _attach_transcript_if_missing(
    video: WebsiteContent,
    base_url: str,
    youtube_id: str,
    summary: dict | None = None,
    write_output: Callable[..., None] = log.info,
) -> None:
    """
    Attach transcript to video if it does not exist.
    Fetches from 3Play API and updates the video metadata.
    """
    if video.metadata["video_files"].get("video_transcript_file"):
        return

    pdf_url = base_url + f"&format_id={PDF_FORMAT_ID}"
    pdf_response = fetch_file(pdf_url)

    if summary:
        summary["transcripts"]["total"] += 1

    if pdf_response:
        file_size = len(pdf_response.getvalue())
        pdf_file = File(pdf_response, name=f"{youtube_id}.pdf")
        filepath = _create_new_content(pdf_file, video, file_size=file_size)
        video.metadata["video_files"]["video_transcript_file"] = filepath

        if summary:
            summary["transcripts"]["updated"] += 1

        write_output(
            "Transcript updated for video, %s and course %s",
            video.title,
            video.website.short_id,
        )
    elif summary:
        summary["transcripts"]["missing"] += 1
        summary["transcripts"]["missing_details"].append(
            (youtube_id, video.website.short_id)
        )


def _attach_captions_if_missing(
    video: WebsiteContent,
    base_url: str,
    youtube_id: str,
    summary: dict | None = None,
    write_output: Callable[..., None] = log.info,
) -> None:
    """
    Attach captions to video if it does not exist.
    Fetches from 3Play API and updates the video metadata.
    """
    if video.metadata["video_files"].get("video_captions_file"):
        return

    webvtt_url = base_url + f"&format_id={WEBVTT_FORMAT_ID}"
    webvtt_response = fetch_file(webvtt_url)
    if summary:
        summary["captions"]["total"] += 1

    if webvtt_response:
        file_size = len(webvtt_response.getvalue())
        vtt_file = File(webvtt_response, name=f"{youtube_id}.webvtt")
        filepath = _create_new_content(vtt_file, video, file_size)
        video.metadata["video_files"]["video_captions_file"] = filepath
        if summary:
            summary["captions"]["updated"] += 1
        write_output(
            "Captions updated for video, %s and course %s",
            video.title,
            video.website.short_id,
        )
    elif summary:
        summary["captions"]["missing"] += 1
        summary["captions"]["missing_details"].append(
            (youtube_id, video.website.short_id)
        )


def sync_video_captions_and_transcripts(
    video: WebsiteContent,
    summary: dict | None = None,
    missing_results: dict | None = None,
    write_output: Callable[..., None] = log.info,
) -> None:
    """
    Fetch captions/transcripts via 3play and either attach them to the video
    metadata or record them as missing.
    """
    youtube_id = video.metadata["video_metadata"]["youtube_id"]
    threeplay_transcript_json = threeplay_transcript_api_request(youtube_id)
    if (
        not threeplay_transcript_json.get("data")
        or len(threeplay_transcript_json.get("data")) == 0
        or threeplay_transcript_json.get("data")[0].get("status") != "complete"
    ):
        if missing_results:
            missing_results["count"] += 1
        write_output(
            "Captions and transcripts not found for video %s, course %s",
            video.title,
            video.website.short_id,
        )
        return

    transcript_id = threeplay_transcript_json["data"][0].get("id")
    media_file_id = threeplay_transcript_json["data"][0].get("media_file_id")
    base_url = transcript_base_url.format(
        media_file_id=media_file_id,
        transcript_id=transcript_id,
        project_id=settings.THREEPLAY_PROJECT_ID,
    )
    # If transcript does not exist
    _attach_transcript_if_missing(video, base_url, youtube_id, summary, write_output)

    # If captions does not exist
    _attach_captions_if_missing(video, base_url, youtube_id, summary, write_output)
    video.skip_sync = True
    video.save()


def upload_to_s3(file_content: File, video: WebsiteContent) -> str:
    """Uploads the captions/transcript file to the S3 bucket"""  # noqa: D401
    s3 = get_boto3_resource("s3")
    new_s3_loc = generate_s3_path(file_content, video.website)
    s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_s3_loc).upload_fileobj(file_content)

    return f"/{new_s3_loc}"


def generate_metadata(
    new_uid: str, new_s3_path: str, file_content: File, video: WebsiteContent
) -> tuple[str, dict]:
    """Generate new metadata for new VTT WebsiteContent object"""
    file_ext = extension_map[get_file_extension(str(file_content))]
    title = f"{video.title} {file_ext['ext']}"
    youtube_id = video.metadata["video_metadata"]["youtube_id"]

    return (
        title,
        {
            "uid": new_uid,
            "file": new_s3_path,
            "title": title,
            "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "ocw_type": "OCWFile",
            "file_type": file_ext["file_type"],
            "description": "",
            "video_files": {"video_thumbnail_file": None},
            "resourcetype": file_ext["resource_type"],
            "video_metadata": {"youtube_id": youtube_id},
            "learning_resource_types": [],
        },
    )


def _create_new_content(
    file_content: File, video: WebsiteContent, file_size: int | None = None
) -> str:
    """
    Create and save a new WebsiteContent object
    for a caption or transcript file.
    """
    new_text_id = str(uuid4())
    new_s3_loc = upload_to_s3(file_content, video)
    title, new_obj_metadata = generate_metadata(
        new_text_id, new_s3_loc, file_content, video
    )
    collection_type = "resource"
    filename = get_dirpath_and_filename(new_s3_loc)[1]
    dirpath = get_content_dirpath("ocw-course-v2", collection_type)

    obj, _ = WebsiteContent.objects.get_or_create(
        website=video.website,
        filename=filename,
        dirpath=dirpath,
        is_page_content=True,
        defaults={
            "metadata": new_obj_metadata,
            "title": title,
            "type": collection_type,
            "text_id": new_text_id,
        },
    )
    obj.metadata["file_size"] = file_size
    obj.file = new_s3_loc
    obj.save()

    return new_s3_loc
