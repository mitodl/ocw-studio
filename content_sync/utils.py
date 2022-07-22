"""Content sync utility functionality"""
import logging
import os
from typing import Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from content_sync.constants import (
    DEV_END,
    DEV_START,
    END_TAG_PREFIX,
    NON_DEV_END,
    NON_DEV_START,
    START_TAG_PREFIX,
)
from main.s3_utils import get_boto3_resource
from websites.constants import WEBSITE_CONTENT_FILETYPE
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig


log = logging.getLogger()


def get_destination_filepath(
    content: WebsiteContent, site_config: SiteConfig
) -> Optional[str]:
    """
    Returns the full filepath where the equivalent file for the WebsiteContent record should be placed
    """
    if content.is_page_content:
        return os.path.join(
            content.dirpath, f"{content.filename}.{WEBSITE_CONTENT_FILETYPE}"
        )
    config_item = site_config.find_item_by_name(name=content.type)
    if config_item is None:
        log.error(
            "Config item not found (content: %s, name value missing from config: %s)",
            (content.id, content.text_id),
            content.type,
        )
        return None
    if config_item.is_file_item():
        return config_item.file_target
    log.error(
        "Invalid config item: is_page_content flag is False, and config item is not 'file'-type (content: %s)",
        (content.id, content.text_id),
    )
    return None


def get_destination_url(
    content: WebsiteContent, site_config: SiteConfig
) -> Optional[str]:
    """
    Returns the URL a given piece of content is expected to be at
    """
    if content.is_page_content:
        filename = "" if content.filename == "_index" else content.filename
        url_with_content = os.path.join(content.dirpath, filename)
        content_dir_prefix = f"{site_config.content_dir}/"
        if url_with_content.startswith(content_dir_prefix):
            url_with_content = url_with_content[len(content_dir_prefix) :]
        return os.path.join("/", url_with_content)
    log.error(
        "Cannot get destination URL because is_page_content is false (content: %s)",
        (content.id, content.text_id),
    )
    return None


def check_mandatory_settings(mandatory_settings):
    """Make sure all mandatory settings are present"""
    missing_settings = []
    for setting_name in mandatory_settings:
        if getattr(settings, setting_name, None) in (
            None,
            "",
        ):
            missing_settings.append(setting_name)
    if missing_settings:
        raise ImproperlyConfigured(
            "The following settings are missing: {}".format(", ".join(missing_settings))
        )


def move_s3_object(from_path, to_path):
    """Move an S3 object from one path to another"""
    s3 = get_boto3_resource("s3")
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    extra_args = {"ACL": "public-read"}
    s3.meta.client.copy(
        {"Bucket": bucket, "Key": from_path}, bucket, to_path, extra_args
    )
    s3.Object(bucket, from_path).delete()


def get_template_vars(env):
    """Get an object with all the template vars we need in pipelines based on env"""
    base_vars = {
        "preview_bucket_name": settings.AWS_PREVIEW_BUCKET_NAME,
        "publish_bucket_name": settings.AWS_PUBLISH_BUCKET_NAME,
        "storage_bucket_name": settings.AWS_STORAGE_BUCKET_NAME,
        "artifacts_bucket_name": "ol-eng-artifacts",
    }
    default_vars = {
        "resource_base_url_draft": "",
        "resource_base_url_live": "",
        "ocw_studio_url": settings.SITE_BASE_URL,
    }
    default_vars.update(base_vars)
    dev_vars = {
        "resource_base_url_draft": settings.RESOURCE_BASE_URL_DRAFT,
        "resource_base_url_live": settings.RESOURCE_BASE_URL_LIVE,
        "ocw_studio_url": "http://10.1.0.102:8043",
    }
    dev_vars.update(base_vars)
    return dev_vars if env == "dev" else default_vars


def check_matching_tags(pipeline_config_file_path, start_tag, end_tag):
    """
    Opens a file and checks to make sure the same number of start_tag and end_tag strings exist in its contents
    Also checks to make sure that start and end tags are properly prefixed and their suffixes match

    Args:
        pipeline_config_file_path (str): The path to a pipeline config file
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        bool: True if the amount of start_tag matches the amount of end_tag in pipeline_config_file, False if not
    """

    start_tags = 0
    end_tags = 0
    if not start_tag.startswith(START_TAG_PREFIX):
        raise ValueError(
            f"{start_tag} is not properly prefixed with {START_TAG_PREFIX}"
        )
    if not end_tag.startswith(END_TAG_PREFIX):
        raise ValueError(f"{end_tag} is not properly prefixed with {END_TAG_PREFIX}")
    if not start_tag.replace(START_TAG_PREFIX, "") == end_tag.replace(
        END_TAG_PREFIX, ""
    ):
        raise ValueError(f"{start_tag} and {end_tag} do not have matching suffixes")
    with open(pipeline_config_file_path) as pipeline_config_file:
        for line in pipeline_config_file:
            if start_tag in line:
                start_tags += 1
            elif end_tag in line:
                end_tags += 1
        equal = start_tags == end_tags
        if not equal:
            raise ValueError(
                f"Number of {start_tag} tags does not match number of {end_tag} tags in {pipeline_config_file_path}"
            )
        return start_tags == end_tags


def strip_lines_between(pipeline_config_file_path, start_tag, end_tag):
    """
    Opens a file, reads the contents and strips out the lines between any matching instances of start_tag and end_tag
    start_tag must start with "# START" followed by a tag and end_tag must start with "# END" followed by the same tag, separated by spaces

    Args:
        pipeline_config_file_path (str): The path to a pipeline config file
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        str: The contents of the file found at pipeline_config_file_path with the lines between start_tag and end_tag stripped out
    """
    check_matching_tags(pipeline_config_file_path, start_tag, end_tag)
    sections_found = 0
    non_dev_sections = [{}]
    lines = []
    with open(pipeline_config_file_path) as pipeline_config_file:
        for num, line in enumerate(pipeline_config_file, 1):
            lines.append(line)
            if start_tag in line:
                non_dev_sections[sections_found] = {"start": num}
            if end_tag in line:
                non_dev_sections[sections_found]["end"] = num
            if "end" in non_dev_sections[sections_found]:
                sections_found += 1
                non_dev_sections.append({})
        non_dev_sections.pop()
        sliced = []
        for num, section in enumerate(non_dev_sections, 1):
            start = 0 if num == 1 else non_dev_sections[num - 1]["end"]
            end = section["start"] - 1
            sliced += lines[start:end]
        start = non_dev_sections[len(non_dev_sections) - 1]["end"]
        end = len(lines)
        if start != end:
            sliced += lines[start:end]
        return "".join(sliced)


def strip_dev_lines(pipeline_config_file_path):
    """
    Runs strip_lines_between for content_sync.utils.constants.DEV_START and DEV_END

    Args:
        pipeline_config_file_path (str): The path to a pipeline config file
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        str: The contents of the file found at pipeline_config_file_path with the lines between DEV_START and DEV_END stripped out
    """
    return strip_lines_between(pipeline_config_file_path, DEV_START, DEV_END)


def strip_non_dev_lines(pipeline_config_file_path):
    """
    Runs strip_lines_between for content_sync.utils.constants.NON_DEV_START and NON_DEV_END

    Args:
        pipeline_config_file_path (str): The path to a pipeline config file
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        str: The contents of the file found at pipeline_config_file_path with the lines between NON_DEV_START and NON_DEV_END stripped out
    """
    return strip_lines_between(pipeline_config_file_path, NON_DEV_START, NON_DEV_END)
