"""This module contains exception handling for videos."""

import logging

import requests

log = logging.getLogger()


def raise_invalid_response_error(video_id: int, response) -> None:
    """Raise an exception for invalid 3Play API responses."""
    error_msg = f"Invalid response from 3Play upload for video {video_id}: {response}"
    log.warning(error_msg)
    raise requests.exceptions.RequestException(error_msg)


def raise_head_request_error(status_code: int, video_title: str):
    """
    Raise an HTTPError for an invalid response during archive_url HEAD request
    when populating video file size.
    """
    error_msg = f"Bad response: {status_code}"
    log.error(
        "Failed to populate file size for video %s: %s",
        video_title,
        error_msg,
    )
    raise requests.HTTPError(error_msg)


def raise_missing_file_metadata_error(filename: str) -> None:
    """
    Raise a ValueError when metadata['file'] is missing
    from a caption or transcript resource.
    """
    error_msg = f"Missing metadata['file'] for {filename}"
    raise ValueError(error_msg)
