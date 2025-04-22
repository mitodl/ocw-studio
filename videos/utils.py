"""
A collection of helper functions for generating s3 file paths and filenames.
This module provides several utility functions that simplify the task of working with file path and name generation
"""  # noqa: E501

import os
import re
from copy import deepcopy
from uuid import uuid4

from django.conf import settings
from django.core.files import File

from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename, get_file_extension, uuid_string
from videos.constants import PDF_FORMAT_ID, WEBVTT_FORMAT_ID
from videos.threeplay_api import fetch_file, threeplay_transcript_api_request
from websites.models import Website, WebsiteContent, WebsiteStarter

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


def fetch_and_update_content(
    video,
    transcript_base_url: str,
    summary: dict,
    missing_results: dict,
    stdout_write: callable,
):
    """
    Fetch captions/transcripts via 3play and either attach them to the video
    metadata or record them as missing. Mutates `summary` and `missing_results_cont`.
    """
    youtube_id = video.metadata["video_metadata"]["youtube_id"]
    threeplay_transcript_json = threeplay_transcript_api_request(youtube_id)

    if (
        not threeplay_transcript_json.get("data")
        or len(threeplay_transcript_json.get("data")) == 0
        or threeplay_transcript_json.get("data")[0].get("status") != "complete"
    ):
        missing_results["count"] += 1
        stdout_write(
            f"Captions and transcripts not found in 3play for video, {video.title} and course {video.website.short_id}"  # noqa: E501
        )
        return

    transcript_id = threeplay_transcript_json["data"][0].get("id")
    media_file_id = threeplay_transcript_json["data"][0].get("media_file_id")

    # If transcript does not exist
    if not video.metadata["video_files"]["video_transcript_file"]:
        url = transcript_base_url.format(
            media_file_id=media_file_id,
            transcript_id=transcript_id,
            project_id=settings.THREEPLAY_PROJECT_ID,
        )
        pdf_url = url + f"&format_id={PDF_FORMAT_ID}"
        pdf_response = fetch_file(pdf_url)
        summary["transcripts"]["total"] += 1

        if pdf_response:
            pdf_file = File(pdf_response, name=f"{youtube_id}.pdf")
            new_filepath = _create_new_content(pdf_file, video)
            video.metadata["video_files"]["video_transcript_file"] = new_filepath
            summary["transcripts"]["updated"] += 1
            stdout_write(
                f"Transcript updated for video, {video.title} and course {video.website.short_id}"  # noqa: E501
            )
        else:
            summary["transcripts"]["missing"] += 1
            summary["transcripts"]["missing_details"].append(
                (youtube_id, video.website.short_id)
            )

    # If captions does not exist
    if not video.metadata["video_files"]["video_captions_file"]:
        url = transcript_base_url.format(
            media_file_id=media_file_id,
            transcript_id=transcript_id,
            project_id=settings.THREEPLAY_PROJECT_ID,
        )
        webvtt_url = url + f"&format_id={WEBVTT_FORMAT_ID}"
        webvtt_response = fetch_file(webvtt_url)
        summary["captions"]["total"] += 1

        if webvtt_response:
            vtt_file = File(webvtt_response, name=f"{youtube_id}.webvtt")
            new_filepath = _create_new_content(vtt_file, video)
            video.metadata["video_files"]["video_captions_file"] = new_filepath
            summary["captions"]["updated"] += 1
            stdout_write(
                f"Captions updated for video, {video.title} and course {video.website.short_id}"  # noqa: E501
            )
        else:
            summary["captions"]["missing"] += 1
            summary["captions"]["missing_details"].append(
                (youtube_id, video.website.short_id)
            )
    video.save()


def upload_to_s3(file_content, video):
    """Uploads the captions/transcript file to the S3 bucket"""  # noqa: D401
    s3 = get_boto3_resource("s3")
    new_s3_loc = generate_s3_path(file_content, video.website)
    s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_s3_loc).upload_fileobj(file_content)

    return f"/{new_s3_loc}"


def generate_metadata(new_uid, new_s3_path, file_content, video):
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


def _create_new_content(file_content, video):
    """Create new WebsiteContent object for caption or transcript using 3play response"""  # noqa: E501
    new_text_id = str(uuid4())
    new_s3_loc = upload_to_s3(file_content, video)
    title, new_obj_metadata = generate_metadata(
        new_text_id, new_s3_loc, file_content, video
    )
    collection_type = "resource"
    filename = get_dirpath_and_filename(new_s3_loc)[1]
    dirpath = get_content_dirpath("ocw-course-v2", collection_type)

    defaults = {
        "metadata": new_obj_metadata,
        "title": title,
        "type": collection_type,
        "text_id": new_text_id,
    }

    new_obj = WebsiteContent.objects.get_or_create(
        website=video.website,
        filename=filename,
        dirpath=dirpath,
        is_page_content=True,
        defaults=defaults,
    )[0]
    new_obj.save()

    return new_s3_loc


def generate_s3_path(file_or_webcontent, website):
    """Generates S3 path for the file"""  # noqa: D401
    if isinstance(file_or_webcontent, WebsiteContent):
        file_or_webcontent = file_or_webcontent.file

    _, new_filename = get_dirpath_and_filename(file_or_webcontent.name)
    new_filename = clean_uuid_filename(new_filename)
    new_filename_ext = get_file_extension(file_or_webcontent.name)

    if new_filename_ext in ["webvtt", "vtt"]:
        new_filename += "_captions"
    elif new_filename_ext == "pdf":
        new_filename += "_transcript"

    new_filename = f"{new_filename.strip(os.path.sep)}.{new_filename_ext}"

    return os.path.join(  # noqa: PTH118
        website.s3_path.strip(os.path.sep), new_filename
    )


def clean_uuid_filename(filename):
    """Removes UUID from filename"""  # noqa: D401
    uuid = "^[0-9A-F]{8}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{12}_"
    uuid_re = re.compile(uuid, re.I)
    return re.split(uuid_re, filename)[-1]


def get_content_dirpath(slug, collection_type):
    """Return folder path for the content based on collection type"""
    starter = WebsiteStarter.objects.get(slug=slug)
    for collection in starter.config["collections"]:
        if collection["name"] != collection_type:
            continue
        return collection["folder"]
    return None


def copy_obj_s3(source_obj: WebsiteContent, dest_course: Website) -> str:
    """Copy source_obj to the S3 bucket of dest_course"""
    s3 = get_boto3_resource("s3")
    new_s3_path = generate_s3_path(source_obj, dest_course)
    s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_s3_path).copy_from(
        CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME.rstrip('/')}/{str(source_obj.file).lstrip('/')}"
    )
    return new_s3_path


def create_new_content(source_obj, to_course):
    """Create new WebsiteContent object from source_obj in to_course,
    or update existing object if it exists.
    """
    new_text_id = uuid_string()
    if source_obj.file:
        new_s3_loc = copy_obj_s3(source_obj, to_course)
        new_dirpath = "content/resources"
        new_filename = get_dirpath_and_filename(new_s3_loc)[1]
    else:
        new_s3_loc = source_obj.file
        new_dirpath = source_obj.dirpath
        new_filename = source_obj.filename
    new_obj_metadata = update_metadata(source_obj, new_text_id, new_s3_loc)
    existing_content = WebsiteContent.objects.filter(
        website=to_course, dirpath=new_dirpath, filename=new_filename
    ).first()
    if existing_content is None:
        new_obj = WebsiteContent.objects.create(
            website=to_course,
            text_id=new_text_id,
            metadata=new_obj_metadata,
            title=source_obj.title,
            type=source_obj.type,
            file=new_s3_loc,
            dirpath=new_dirpath,
            filename=new_filename,
            is_page_content=True,
        )
        new_obj.save()
    else:
        existing_content.metadata = new_obj_metadata
        existing_content.title = source_obj.title
        existing_content.type = source_obj.type
        existing_content.file = new_s3_loc
        existing_content.dirpath = new_dirpath
        existing_content.filename = new_filename
        existing_content.is_page_content = True
        existing_content.save()
    return new_obj if existing_content is None else existing_content


def update_metadata(source_obj, new_uid, new_s3_path):
    """Generate updated metadata for new WebsiteContent object"""
    new_metadata = deepcopy(source_obj.metadata)
    new_metadata["uid"] = new_uid
    new_metadata["file"] = str(new_s3_path).lstrip("/")
    return new_metadata
