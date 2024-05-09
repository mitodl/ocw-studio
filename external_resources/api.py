import logging
from typing import Optional

import requests

from external_resources.exceptions import CheckFailedError
from websites.models import WebsiteContent

log = logging.getLogger()

STATUS_CODE_WHITELIST = [401, 402, 403, 429]


def is_url_broken(url: str) -> tuple[bool, Optional[int]]:
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
    external_resoure: WebsiteContent,
) -> tuple[bool, Optional[int]]:
    url = external_resoure.metadata.get("external_url", "")
    return is_url_broken(url)


def is_backup_url_broken(
    external_resoure: WebsiteContent,
) -> tuple[bool, Optional[int]]:
    url = external_resoure.metadata.get("backup_url", "")
    return is_url_broken(url)
