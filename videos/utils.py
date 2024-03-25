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
from videos.models import WebsiteContent
from websites.models import Website, WebsiteStarter


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
    )  # noqa: PTH118, RUF100


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
