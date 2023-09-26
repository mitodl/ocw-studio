"""Content sync utility functionality"""
import logging
import os
from typing import Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from content_sync.constants import (
    DEV_END,
    DEV_ENDPOINT_URL,
    DEV_START,
    END_TAG_PREFIX,
    NON_DEV_END,
    NON_DEV_START,
    OFFLINE_END,
    OFFLINE_START,
    ONLINE_END,
    ONLINE_START,
    START_TAG_PREFIX,
    TARGET_OFFLINE,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from main.s3_utils import get_boto3_resource
from main.utils import is_dev
from websites.constants import WEBSITE_CONTENT_FILETYPE
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig

log = logging.getLogger()


def get_destination_filepath(
    content: WebsiteContent, site_config: SiteConfig
) -> Optional[str]:
    """
    Returns the full filepath where the equivalent file for the WebsiteContent record should be placed
    """  # noqa: E501, D401
    if content.is_page_content:
        return os.path.join(  # noqa: PTH118
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
        "Invalid config item: is_page_content flag is False, and config item is not 'file'-type (content: %s)",  # noqa: E501
        (content.id, content.text_id),
    )
    return None


def get_destination_url(
    content: WebsiteContent, site_config: SiteConfig
) -> Optional[str]:
    """
    Returns the URL a given piece of content is expected to be at
    """  # noqa: D401
    if content.is_page_content:
        filename = "" if content.filename == "_index" else content.filename
        url_with_content = os.path.join(content.dirpath, filename)  # noqa: PTH118
        content_dir_prefix = f"{site_config.content_dir}/"
        if url_with_content.startswith(content_dir_prefix):
            url_with_content = url_with_content[len(content_dir_prefix) :]
        return os.path.join("/", url_with_content)  # noqa: PTH118
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
            missing_settings.append(setting_name)  # noqa: PERF401
    if missing_settings:
        msg = f"The following settings are missing: {', '.join(missing_settings)}"
        raise ImproperlyConfigured(msg)


def move_s3_object(from_path, to_path):
    """Move an S3 object from one path to another"""
    s3 = get_boto3_resource("s3")
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    extra_args = {"ACL": "public-read"}
    s3.meta.client.copy(
        {"Bucket": bucket, "Key": from_path}, bucket, to_path, extra_args
    )
    s3.Object(bucket, from_path).delete()


def get_common_pipeline_vars():
    """Get an object with all the template vars we need in pipelines based on env"""
    pipeline_vars = {
        "preview_bucket_name": settings.AWS_PREVIEW_BUCKET_NAME,
        "publish_bucket_name": settings.AWS_PUBLISH_BUCKET_NAME,
        "offline_preview_bucket_name": settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME,
        "offline_publish_bucket_name": settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME,
        "storage_bucket_name": settings.AWS_STORAGE_BUCKET_NAME,
        "artifacts_bucket_name": "ol-eng-artifacts",
        "static_api_base_url_draft": settings.OCW_STUDIO_DRAFT_URL,
        "static_api_base_url_live": settings.OCW_STUDIO_LIVE_URL,
        "resource_base_url_draft": "",
        "resource_base_url_live": "",
    }
    if is_dev():
        pipeline_vars["static_api_base_url_draft"] = (
            settings.STATIC_API_BASE_URL_DRAFT or settings.OCW_STUDIO_DRAFT_URL
        )
        pipeline_vars["static_api_base_url_live"] = (
            settings.STATIC_API_BASE_URL_LIVE or settings.OCW_STUDIO_LIVE_URL
        )
        pipeline_vars.update(
            {
                "resource_base_url_draft": settings.RESOURCE_BASE_URL_DRAFT,
                "resource_base_url_live": settings.RESOURCE_BASE_URL_LIVE,
            }
        )
    return pipeline_vars


def get_cli_endpoint_url():
    return f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""


def get_ocw_studio_api_url():
    return "http://10.1.0.102:8043" if is_dev() else settings.SITE_BASE_URL


def get_publishable_sites(version: str):
    publish_date_field = (
        "publish_date" if version == VERSION_LIVE else "draft_publish_date"
    )
    # Get all sites, minus any sites that have never been successfully published
    sites = Website.objects.exclude(
        Q(**{f"{publish_date_field}__isnull": True}) | Q(url_path__isnull=True)
    )
    if version == VERSION_LIVE:
        sites = sites.exclude(unpublish_status__isnull=False)
    return sites.prefetch_related("starter")


def get_site_content_branch(version: str):
    return (
        settings.GIT_BRANCH_PREVIEW
        if version == VERSION_DRAFT
        else settings.GIT_BRANCH_RELEASE
    )


def get_theme_branch():
    """
    Gets the branch to use of ocw-hugo-themes in pipelines, defaulting to settings.GITHUB_WEBHOOK_BRANCH
    if settings.ENVIRONMENT is anything but "dev," otherwise take the value of settings.OCW_HUGO_THEMES_BRANCH
    """  # noqa: E501, D401
    github_webhook_branch = settings.GITHUB_WEBHOOK_BRANCH
    return (
        (settings.OCW_HUGO_THEMES_BRANCH or github_webhook_branch)
        if is_dev()
        else github_webhook_branch
    )


def get_hugo_arg_string(build_target, pipeline_name, default_args, override_args=None):
    """
    Builds a string of arguments to be passed to the hugo command inserted into pipelines

    Args:
        build_target (str): The build target (online / offline)
        pipeline_name (str): The name of the pipeline (draft / live)
        default_args (dict): A dictionary of default args for the given context
        override_args (str): (Optional) A string of arg overrides passed when executing a pipeline management command

    Returns:
        str: A string of arguments that can be appended to the hugo command in a pipeline
    """  # noqa: E501, D401
    hugo_args = default_args.copy()
    if pipeline_name == VERSION_DRAFT:
        hugo_args["--buildDrafts"] = ""
    if override_args:
        split_override_args = override_args.split(" ")
        for index, arg in enumerate(split_override_args):
            next_arg = (
                split_override_args[index + 1]
                if (index < len(split_override_args) - 1)
                else ""
            )
            if arg.startswith("-") and not next_arg.startswith("-"):
                hugo_args[arg] = next_arg
                # If the build target is offline, / is the only value that makes sense for --baseURL  # noqa: E501
                if arg == "--baseURL" and build_target == TARGET_OFFLINE:
                    hugo_args[arg] = "/"
            elif arg.startswith("-"):
                hugo_args[arg] = ""
    hugo_arg_strings = []
    for hugo_arg_key, hugo_arg_value in hugo_args.items():
        value = f" {hugo_arg_value}" if hugo_arg_value != "" else ""
        hugo_arg_strings.append(f"{hugo_arg_key}{value}")
    return " ".join(hugo_arg_strings)


def check_matching_tags(pipeline_config, start_tag, end_tag):
    """
    Iterates lines in pipeline_config and checks to make sure the same number of start_tag and end_tag strings exist in its contents
    Also checks to make sure that start and end tags are properly prefixed and their suffixes match

    Args:
        pipeline_config (str): A pipeline config in string format
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        bool: True if the amount of start_tag matches the amount of end_tag in pipeline_config_file, False if not
    """  # noqa: E501, D401

    start_tags = 0
    end_tags = 0
    if not start_tag.startswith(START_TAG_PREFIX):
        msg = f"{start_tag} is not properly prefixed with {START_TAG_PREFIX}"
        raise ValueError(msg)
    if not end_tag.startswith(END_TAG_PREFIX):
        msg = f"{end_tag} is not properly prefixed with {END_TAG_PREFIX}"
        raise ValueError(msg)
    if start_tag.replace(START_TAG_PREFIX, "") != end_tag.replace(END_TAG_PREFIX, ""):
        msg = f"{start_tag} and {end_tag} do not have matching suffixes"
        raise ValueError(msg)
    for line in pipeline_config.splitlines():
        if start_tag in line:
            start_tags += 1
        elif end_tag in line:
            end_tags += 1
    equal = start_tags == end_tags
    if not equal:
        msg = f"Number of {start_tag} tags does not match number of {end_tag} tags in {pipeline_config}"  # noqa: E501
        raise ValueError(msg)
    return start_tags == end_tags


def strip_lines_between(pipeline_config, start_tag, end_tag):
    """
    Strips out the lines between any matching instances of start_tag and end_tag from pipeline_config

    start_tag must start with "# START" followed by a tag and end_tag must start
    with "# END" followed by the same tag, separated by spaces

    Args:
        pipeline_config (str): A pipeline config in string format
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        str: The contents of pipeline_config with the lines between start_tag and end_tag stripped out
    """  # noqa: E501, D401
    check_matching_tags(pipeline_config, start_tag, end_tag)
    if start_tag not in pipeline_config and end_tag not in pipeline_config:
        return pipeline_config
    sections_found = 0
    section_matches = [{}]
    lines = []
    for num, line in enumerate(pipeline_config.splitlines(), 1):
        lines.append(line)
        if start_tag in line:
            section_matches[sections_found] = {"start": num}
        if end_tag in line:
            section_matches[sections_found]["end"] = num
        if "end" in section_matches[sections_found]:
            sections_found += 1
            section_matches.append({})
    section_matches.pop()
    sliced = []
    for num, section in enumerate(section_matches, 1):
        start = 0 if num == 1 else section_matches[num - 2]["end"]
        end = section["start"] - 1
        sliced += lines[start:end]
    start = section_matches[len(section_matches) - 1]["end"]
    end = len(lines)
    if start != end:
        sliced += lines[start:end]
    return "\n".join(sliced)


def strip_dev_lines(pipeline_config):
    """
    Runs strip_lines_between for content_sync.utils.constants.DEV_START and DEV_END

    Args:
        pipeline_config (str): A pipeline config in string format

    Returns:
        str: The contents of pipeline_config with the lines between DEV_START and DEV_END stripped out
    """  # noqa: E501, D401
    return strip_lines_between(pipeline_config, DEV_START, DEV_END)


def strip_non_dev_lines(pipeline_config):
    """
    Runs strip_lines_between for content_sync.utils.constants.NON_DEV_START and NON_DEV_END

    Args:
        pipeline_config (str): A pipeline config in string format

    Returns:
        str: The contents of pipeline_config with the lines between NON_DEV_START and NON_DEV_END stripped out
    """  # noqa: E501, D401
    return strip_lines_between(pipeline_config, NON_DEV_START, NON_DEV_END)


def strip_offline_lines(pipeline_config):
    """
    Runs strip_lines_between for content_sync.utils.constants.OFFLINE_START and OFFLINE_END

    Args:
        pipeline_config (str): A pipeline config in string format

    Returns:
        str: The contents of pipeline_config with the lines between OFFLINE_START and OFFLINE_END stripped out
    """  # noqa: E501, D401
    return strip_lines_between(pipeline_config, OFFLINE_START, OFFLINE_END)


def strip_online_lines(pipeline_config):
    """
    Runs strip_lines_between for content_sync.utils.constants.NON_DEV_START and NON_DEV_END

    Args:
        pipeline_config (str): A pipeline config in string format
        start_tag (str): The start tag delimiter
        end_tag (str): The end tag delimiter

    Returns:
        str: The contents of pipeline_config with the lines between ONLINE_START and ONLINE_END stripped out
    """  # noqa: E501, D401
    return strip_lines_between(pipeline_config, ONLINE_START, ONLINE_END)
