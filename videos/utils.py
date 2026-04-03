"""
A collection of helper functions for generating s3 file paths and filenames.
This module provides several utility functions that simplify the task of working with file path and name generation
"""  # noqa: E501

import os
import re
from copy import deepcopy

from django.conf import settings

from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename, get_file_extension, uuid_string
from videos.constants import YT_LIST_BATCH_SIZE
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.utils import get_dict_field, set_dict_field


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


def get_course_tag(website: Website) -> str:
    """
    Get the course URL slug from the website's url_path.

    Args:
        website: Website instance

    Returns:
        str: The course URL slug (e.g., '18-01-fall-2020')
    """
    url_path = website.url_path or ""
    root_url_path = website.get_site_root_path()

    if root_url_path and url_path.startswith(f"{root_url_path}/"):
        return url_path.removeprefix(f"{root_url_path}/")
    return url_path


def parse_tags(tags: str) -> list[str]:
    """
    Parse a comma-separated tag string into a list of cleaned, normalized tags.

    Args:
        tags (str): Comma-separated tag string

    Returns:
        list[str]: List of cleaned, non-empty, lowercase tags
    """
    return [tag.strip().lower() for tag in tags.split(",") if tag.strip()]


def get_tags_with_course(metadata: dict, course_slug: str) -> str:
    """
    Get video tags with the course URL slug appended.
    Tags are normalized (lowercased, stripped) and deduplicated.

    Args:
        metadata (dict): The WebsiteContent metadata dictionary
        course_slug (str): The course URL slug to add as a tag

    Returns:
        str: Comma-separated tags with course slug appended,
             sorted alphabetically (lowercase)
    """
    existing_tags = get_dict_field(metadata, settings.YT_FIELD_TAGS) or ""

    # remove duplicates and empty tags
    all_tags = set(parse_tags(existing_tags))

    # Add course slug if provided and not empty
    if course_slug and course_slug not in all_tags:
        all_tags.add(course_slug.strip().lower())

    # Sort alphabetically (tags are already lowercase)
    sorted_tags = sorted(all_tags)
    return ", ".join(sorted_tags)


def fetch_youtube_snippets(youtube, youtube_ids):
    """
    Fetch YouTube video snippets in batches of up to 50 IDs per API call.

    Each call costs 1 quota unit regardless of the number of IDs (up to 50).
    The number of quota units consumed is:
    ``math.ceil(len(youtube_ids) / YT_LIST_BATCH_SIZE) * QUOTA_COST_VIDEO_LIST``.

    Args:
        youtube: YouTubeApi instance
        youtube_ids: List of YouTube video IDs

    Returns:
        dict: Mapping of youtube_id -> snippet dict for found videos
    """
    snippets = {}
    for i in range(0, len(youtube_ids), YT_LIST_BATCH_SIZE):
        batch = youtube_ids[i : i + YT_LIST_BATCH_SIZE]
        response = (
            youtube.client.videos().list(part="snippet", id=",".join(batch)).execute()
        )
        for item in response.get("items", []):
            snippets[item["id"]] = item["snippet"]
    return snippets


def process_video_tags(video_resource, snippet, youtube, *, add_course_tag):
    """
    Merge YouTube and DB tags for a single video resource then persist.

    Updates YouTube via ``videos().update`` if tags changed, and always saves
    the merged tag string to the DB. Mutates ``snippet["tags"]`` in-place so
    callers sharing the same snippet dict across multiple resources for the
    same YouTube video accumulate tags correctly.

    Args:
        video_resource: WebsiteContent instance
        snippet: YouTube snippet dict (from the videos.list response)
        youtube: YouTubeApi instance
        add_course_tag: If True, add the course URL slug as a tag

    Returns:
        str: ``"success"`` if YouTube was updated, ``"skip"`` otherwise
    """

    yt_id = get_dict_field(video_resource.metadata, settings.YT_FIELD_ID)
    course_slug = get_course_tag(video_resource.website)

    youtube_tags = snippet.get("tags", [])
    db_tags_str = get_dict_field(video_resource.metadata, settings.YT_FIELD_TAGS)
    db_tags = set(parse_tags(db_tags_str or ""))

    yt_tags_normalized = (
        set().union(*(parse_tags(t) for t in youtube_tags)) if youtube_tags else set()
    )
    merged = yt_tags_normalized | db_tags
    if add_course_tag and course_slug and course_slug not in merged:
        merged.add(course_slug)

    merged_str = ", ".join(sorted(merged))
    merged_list = parse_tags(merged_str)

    # Detect formatting issues (e.g., commas in a single YouTube tag like "a, b")
    has_formatting_issues = any("," in tag for tag in youtube_tags)
    tags_changed = merged != yt_tags_normalized or has_formatting_issues

    if tags_changed:
        snippet["tags"] = merged_list
        youtube.client.videos().update(
            part="snippet",
            body={"id": yt_id, "snippet": snippet},
        ).execute()

    set_dict_field(video_resource.metadata, settings.YT_FIELD_TAGS, merged_str)
    video_resource.save(update_fields=["metadata"])

    return "success" if tags_changed else "skip"
