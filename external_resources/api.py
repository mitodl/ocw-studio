import logging
from typing import Optional

import requests

from external_resources.exceptions import CheckFailedError
from websites.models import WebsiteContent

log = logging.getLogger()


def is_url_broken(url: str) -> tuple[bool, Optional[int]]:
    """Check if provided url is broken"""
    if url.strip() == "":
        return False, None

    log.debug("Making a HEAD request for url: %s", url)

    try:
        response = requests.head(url, allow_redirects=True, timeout=30)
    except Exception as ex:
        log.debug(ex)
        raise CheckFailedError from ex

    if 400 <= response.status_code < 600:  # noqa: PLR2004
        return True, response.status_code

    return False, response.status_code


def is_external_url_broken(
    external_resource: WebsiteContent,
) -> tuple[bool, Optional[int]]:
    """Check if external url of the provided WebsiteContent is broken"""
    url = external_resource.metadata.get("external_url", "")
    return is_url_broken(url)


def is_backup_url_broken(
    external_resource: WebsiteContent,
) -> tuple[bool, Optional[int]]:
    """Check if backup url of the provided WebsiteContent is broken"""
    url = external_resource.metadata.get("backup_url", "")
    return is_url_broken(url)
