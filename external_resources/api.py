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
    Submit the external resource URL to the Wayback Machine and
    return the job_id or status_ext
    """
    job_id = None
    status_ext = None

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
    params = {
        "url": url,
        "skip_first_archive": "1",
        "capture_outlinks": "0",
    }

    try:
        response = requests.post(api_url, headers=headers, data=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        job_id = result.get("job_id")

        if not job_id:
            status_ext = result.get("status_ext")
            log.error("No job_id returned from Wayback Machine for URL %s", url)
    except Exception:
        log.exception("Failed to submit URL to Wayback Machine: %s", url)

    return {"job_id": job_id, "status_ext": status_ext}


def check_wayback_jobs_status_batch(job_ids: list[str]) -> list[dict]:
    """
    Check the status of multiple Wayback Machine jobs in batch.
    """
    if not job_ids:
        return []

    api_url = "https://web.archive.org/save/status"
    headers = {
        "Accept": "application/json",
        "Authorization": (
            f"LOW {settings.WAYBACK_MACHINE_ACCESS_KEY}:"
            f"{settings.WAYBACK_MACHINE_SECRET_KEY}"
        ),
    }
    params = {
        "job_ids": ",".join(job_ids),
    }
    try:
        response = requests.post(api_url, headers=headers, data=params, timeout=30)
        response.raise_for_status()
        result = response.json()
    except Exception:
        log.exception(
            "Failed to check Wayback Machine job statuses for job IDs: %s", job_ids
        )
        return []
    else:
        return result
