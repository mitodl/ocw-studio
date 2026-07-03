import logging
from collections.abc import Callable
from io import BytesIO
from typing import TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.core.files import File

from main.s3_utils import get_boto3_resource
from main.utils import get_base_filename, get_dirpath_and_filename, get_file_extension
from videos.constants import PDF_FORMAT_ID, WEBVTT_FORMAT_ID
from videos.threeplay_api import fetch_file, threeplay_transcript_api_request
from videos.utils import generate_s3_path, get_content_dirpath
from websites.api import sync_website_content_references
from websites.models import WebsiteContent

if TYPE_CHECKING:
    from collections.abc import Callable

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


def _append_resource_to_video_files(
    video: WebsiteContent,
    resource_field: str,
    text_id: str,
) -> None:
    """
    Append a caption/transcript resource id to the video's ``_resources``
    relation field in video_files metadata.

    Preserves any existing entries (e.g. other-language variants already
    linked from GDrive) instead of overwriting them.  The legacy ``_file``
    fields in stored metadata are left untouched.
    """
    if not isinstance(video.metadata, dict):
        video.metadata = {}
    vf = video.metadata.setdefault("video_files", {})
    existing_resources = vf.get(resource_field)
    if isinstance(existing_resources, dict) and existing_resources.get("content"):
        content = existing_resources["content"]
        content_list = [content] if isinstance(content, str) else list(content)
        if text_id not in content_list:
            existing_resources["content"] = [*content_list, text_id]
    else:
        vf[resource_field] = {"content": [text_id], "website": video.website.name}


def _threeplay_resource_already_linked(
    video: WebsiteContent, resource_field: str, filename_prefix: str
) -> bool:
    """Return True if the 3Play-generated resource is already in the content list."""
    existing_content = (
        video.metadata["video_files"].get(resource_field, {}).get("content") or []
    )
    return bool(
        isinstance(existing_content, list)
        and existing_content
        and WebsiteContent.objects.filter(
            website=video.website,
            text_id__in=existing_content,
            filename__startswith=filename_prefix,
        ).exists()
    )


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
    if _threeplay_resource_already_linked(
        video, "video_transcript_resources", f"{youtube_id}_transcript"
    ):
        return

    pdf_url = base_url + f"&format_id={PDF_FORMAT_ID}"
    pdf_response = fetch_file(pdf_url)

    if summary:
        summary["transcripts"]["total"] += 1

    if pdf_response:
        file_size = len(pdf_response.getvalue())
        pdf_file = File(pdf_response, name=f"{youtube_id}.pdf")
        text_id = _create_new_content(pdf_file, video, file_size=file_size)
        _append_resource_to_video_files(video, "video_transcript_resources", text_id)
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
    if _threeplay_resource_already_linked(
        video, "video_captions_resources", f"{youtube_id}_captions"
    ):
        return

    webvtt_url = base_url + f"&format_id={WEBVTT_FORMAT_ID}"
    webvtt_response = fetch_file(webvtt_url)
    if summary:
        summary["captions"]["total"] += 1

    if webvtt_response:
        file_size = len(webvtt_response.getvalue())
        vtt_file = File(webvtt_response, name=f"{youtube_id}.webvtt")
        text_id = _create_new_content(vtt_file, video, file_size)
        _append_resource_to_video_files(video, "video_captions_resources", text_id)
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


def link_threeplay_files_as_resources(video, video_resource: WebsiteContent) -> bool:
    """
    Create caption/transcript WebsiteContent resources from a Video's
    already-downloaded 3Play files (``webvtt_transcript_file`` /
    ``pdf_transcript_file``) and link them on the video resource's
    ``_resources`` relation fields.

    The created resources follow the ``{base}_captions`` / ``{base}_transcript``
    filename convention (no language suffix — 3Play transcripts are English), so
    subsequent auto-link passes and ``Video.caption_transcript_resources()``
    lookups find them.  The legacy ``_file`` fields in stored metadata are left
    untouched.

    Returns True if the video resource's metadata was modified.
    """
    base = get_base_filename(video_resource.filename or "")
    if not base:
        return False
    changed = False
    for field_file, resource_field, extension in (
        (video.webvtt_transcript_file, "video_captions_resources", "vtt"),
        (video.pdf_transcript_file, "video_transcript_resources", "pdf"),
    ):
        if not (field_file and field_file.name):
            continue
        with field_file.open("rb") as file_handle:
            content_bytes = file_handle.read()
        file_obj = File(BytesIO(content_bytes), name=f"{base}.{extension}")
        _, text_id = _create_new_content(
            file_obj, video_resource, file_size=len(content_bytes)
        )
        _append_resource_to_video_files(video_resource, resource_field, text_id)
        changed = True
    return changed


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
    sync_website_content_references(video)


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
    Returns the new resource's text_id.
    """
    new_text_id = str(uuid4())
    new_s3_loc = upload_to_s3(file_content, video)
    title, new_obj_metadata = generate_metadata(
        new_text_id, new_s3_loc, file_content, video
    )
    collection_type = "resource"
    # Append the extension suffix (e.g. _vtt/_pdf) so the created resource
    # matches the {base}_captions*_vtt / {base}_transcript*_pdf filename
    # convention used by gdrive ingestion and the auto-link lookups.
    filename = get_dirpath_and_filename(new_s3_loc)[1]
    extension = get_file_extension(new_s3_loc)
    if extension:
        filename = f"{filename}_{extension}"
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

    return str(obj.text_id)
