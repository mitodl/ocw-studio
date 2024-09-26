"""External Resources API"""

import logging
from typing import Optional

import requests

from external_resources.constants import (
    RESOURCE_BROKEN_STATUS_END,
    RESOURCE_BROKEN_STATUS_START,
    USER_AGENT_STRING,
    USER_AGENT_TIMEOUT,
)
from external_resources.exceptions import CheckFailedError
from main import settings
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


def submit_url_to_wayback(
    url: str,
) -> Optional[str]:
    """
    Submit the external resource URL to the Wayback Machine and return the job_id
    """
    if not url:
        return None

    api_url = "https://web.archive.org/save"
    headers = {
        "Accept": "application/json",
        "Authorization": (
            f"LOW {settings.WAYBACK_MACHINE_ACCESS_KEY}:"
            f"{settings.WAYBACK_MACHINE_SECRET_KEY}"
        ),
    }
    data = {"url": url}

    try:
        response = requests.post(api_url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        job_id = result.get("job_id")
        if job_id:
            return job_id
        else:
            log.error("No job_id returned from Wayback Machine for URL %s", url)
            return None
    except Exception:
        log.exception("Failed to submit URL to Wayback Machine: %s", url)
        return None


def check_external_resource_wayback_job_status(job_id: str) -> Optional[dict]:
    """
    Check the status of a Wayback Machine job and update the resource state accordingly
    """
    if not job_id:
        return None

    api_url = f"https://web.archive.org/save/status/{job_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": (
            f"LOW {settings.WAYBACK_MACHINE_ACCESS_KEY}:"
            f"{settings.WAYBACK_MACHINE_SECRET_KEY}"
        ),
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
    except Exception:
        log.exception("Failed to check Wayback Machine job status: %s", job_id)
        return None
    else:
        return result
