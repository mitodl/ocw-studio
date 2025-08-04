"""This module contains exception handling for videos."""

import logging

import requests

log = logging.getLogger()


def raise_invalid_response_error(video_id: int, response) -> None:
    """Raise an exception for invalid 3Play API responses."""
    error_msg = f"Invalid response from 3Play upload for video {video_id}: {response}"
    log.warning(error_msg)
    raise requests.exceptions.RequestException(error_msg)
