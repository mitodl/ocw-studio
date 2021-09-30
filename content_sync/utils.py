"""Content sync utility functionality"""
import logging
import os
from typing import Optional

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
        return url_with_content
    log.error(
        "Cannot get destination URL because is_page_content is false (content: %s)",
        (content.id, content.text_id),
    )
    return None
