"""
A collection of helper functions for generating s3 file paths and filenames.
This module provides several utility functions that simplify the task of working with file path and name generation
"""
import os
import re

from main.utils import get_dirpath_and_filename, get_file_extension
from videos.models import WebsiteContent


def generate_s3_path(file_or_webcontent, website):
    """Generates S3 path for the file"""
    if isinstance(file_or_webcontent, WebsiteContent):
        file_or_webcontent = file_or_webcontent.file

    _, new_filename = get_dirpath_and_filename(file_or_webcontent.name)
    new_filename = clean_uuid_filename(new_filename)
    new_filename_ext = get_file_extension(file_or_webcontent.name)

    if new_filename_ext in ["webvtt", "vtt"]:
        new_filename += "_captions"
    elif new_filename_ext == "pdf":
        new_filename += "_transcript"

    new_filename = f"{new_filename.strip('/')}.{new_filename_ext}"

    return os.path.join(website.s3_path.strip(os.sep), new_filename)


def clean_uuid_filename(filename):
    """Removes UUID from filename"""
    uuid = "^[0-9A-F]{8}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{12}_"
    uuid_re = re.compile(uuid, re.I)
    return re.split(uuid_re, filename)[-1]
