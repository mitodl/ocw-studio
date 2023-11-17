"""Common fixtures for ocw-studio"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture()
def drf_client():
    """DRF API anonymous test client"""
    return APIClient()


@pytest.fixture()
def preexisting_captions_filenames():
    """
    Filenames for gdrive files and resources as they relate to
    preexisting captions.

    Do not change unless you update the logic that associates
    preexisting captions with videos.
    """
    return {
        "gdrive": {
            "video": "file.mp4",
            "captions": "file_captions.vtt",
            "transcript": "file_transcript.pdf",
        },
        "website_content": {
            "video": "file_mp4",
            "captions": "file_captions_vtt",
            "transcript": "file_transcript_pdf",
        },
    }
