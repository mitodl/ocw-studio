"""Tests for videos.utils"""
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from videos.utils import clean_uuid_filename, generate_s3_path, get_content_dirpath
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)

# pylint:disable=redefined-outer-name
pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("use_content", [True, False])
@pytest.mark.parametrize(
    ("file_extension", "expected_postfix"),
    [("vtt", "_captions"), ("webvtt", "_captions"), ("pdf", "_transcript")],
)
def test_generate_s3_path(use_content, file_extension, expected_postfix):
    """Test generate_s3_path generates appropriate paths for captions."""

    website = WebsiteFactory.create()
    filename = str(uuid4())
    file = SimpleUploadedFile(
        f"/courses/{website.name}/{filename}-file.{file_extension}", b"Nothing here."
    )
    expected_new_path = f'{website.s3_path.strip("/")}/{filename}-file{expected_postfix}.{file_extension}'

    if use_content:
        file_or_content = WebsiteContentFactory.create(website=website, file=file)
    else:
        file_or_content = file

    new_path = generate_s3_path(file_or_content, website)

    assert new_path == expected_new_path


@pytest.mark.parametrize(
    ("filename", "expected_result"),
    [
        (f"{uuid4()}_file.ext", "file.ext"),
        ("file.ext", "file.ext"),
    ],
)
def test_clean_uuid_filename(filename, expected_result):
    """Test clean_uuid_filename strips uuid from filename"""
    assert clean_uuid_filename(filename) == expected_result


def test_get_content_dirpath():
    """Test get_content_dirpath returns the folder of the collection_type"""
    starter = WebsiteStarterFactory.create()

    dirpath = get_content_dirpath(starter.slug, "resource")

    assert dirpath == "content/resource"
