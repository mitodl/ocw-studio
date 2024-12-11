"""External Resources API"""

import logging
from typing import Optional

import requests

from external_resources.constants import (
    RESOURCE_BROKEN_STATUS_END,
    RESOURCE_BROKEN_STATUS_START,
    USER_AGENT_STRING,
    USER_AGENT_TIMEOUT,
    WAYBACK_API_URL,
    WAYBACK_CHECK_STATUS_URL,
    WAYBACK_HEADERS,
)
from external_resources.exceptions import CheckFailedError
from websites.models import WebsiteContent

log = logging.getLogger()


def is_url_broken(url: str) -> tuple[bool, Optional[int]]:
    """Check if provided url is broken"""
    if url.strip() == "":
        return False, None

    log.debug("Making a HEAD request for url: %s", url)

    try:
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=USER_AGENT_TIMEOUT,
            headers={
                "Accept": "*/*",
                "User-Agent": USER_AGENT_STRING,
            },
        )
    except Exception as ex:
        log.debug(ex)
        raise CheckFailedError from ex

    if (
        response.status_code >= RESOURCE_BROKEN_STATUS_START
        and response.status_code < RESOURCE_BROKEN_STATUS_END
    ):
        return True, response.status_code

    return False, response.status_code


def is_external_url_broken(
    external_resource: WebsiteContent,
) -> tuple[bool, Optional[int]]:
    """Check if external url of the provided WebsiteContent is broken"""
    url = external_resource.metadata.get("external_url", "")
    return is_url_broken(url)


def make_wayback_request(url: str, params: dict, headers: dict) -> dict:
    """
    Make an API request to the Wayback Machine and return the response data.
    """
    try:
        response = requests.post(url, headers=headers, data=params, timeout=30)
        response_data = response.json()
        if "message" in response_data:
            log.warning(
                "Wayback Machine response message: %s", response_data["message"]
            )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        log.exception("Error during Wayback Machine request to %s", url)
        raise
    else:
        return response_data


def submit_url_to_wayback(
    url: str,
) -> Optional[str]:
    """
    Submit the external resource URL to the Wayback Machine and
    return the response
    """
    params = {
        "url": url,
        "skip_first_archive": "1",
    }
    return make_wayback_request(WAYBACK_API_URL, params, WAYBACK_HEADERS)


def check_wayback_jobs_status_batch(job_ids: list[str]) -> list[dict]:
    """
    Check the status of multiple Wayback Machine jobs in batch.
    """
    if not job_ids:
        return []

    params = {
        "job_ids": ",".join(job_ids),
    }
    return make_wayback_request(WAYBACK_CHECK_STATUS_URL, params, WAYBACK_HEADERS)
