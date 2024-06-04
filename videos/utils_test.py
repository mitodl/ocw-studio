"""Tests for videos.utils"""

from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from videos.utils import (
    clean_uuid_filename,
    create_new_content,
    generate_s3_path,
    get_content_dirpath,
    get_subscribe_url,
    update_metadata,
)
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


def test_create_new_content(mocker):
    """Test that create_new_content creates or updates the resource correctly."""
    source_course = WebsiteFactory.create()
    destination_course = WebsiteFactory.create()
    source_content = WebsiteContentFactory.create(
        website=source_course, file="source_file"
    )

    mock_copy_obj_s3 = mocker.patch(
        "videos.utils.copy_obj_s3", return_value="new_s3_loc"
    )
    mock_get_dirpath_and_filename = mocker.patch(
        "videos.utils.get_dirpath_and_filename",
        return_value=["new_dirpath", "new_filename"],
    )
    mock_uuid_string = mocker.patch("videos.utils.uuid_string", return_value="new-uuid")
    new_content = create_new_content(source_content, destination_course)

    assert new_content.website == destination_course
    assert new_content.title == source_content.title
    assert new_content.type == source_content.type
    assert new_content.text_id == "new-uuid"
    expected_metadata = update_metadata(source_content, "new-uuid", "new_s3_loc")
    assert new_content.metadata == expected_metadata
    assert new_content.file.name == "new_s3_loc"
    assert new_content.dirpath == "content/resources"
    assert new_content.filename == "new_filename"

    mock_copy_obj_s3.assert_called_once_with(source_content, destination_course)
    mock_get_dirpath_and_filename.assert_called_once_with("new_s3_loc")
    mock_uuid_string.assert_called_once()


def test_get_subscribe_url(mocker):
    """Test get_subscribe_url to format ConfirmSubscription url correctly"""

    mocker.patch("django.conf.settings.AWS_REGION", "us-east-1")
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", "1234567890")

    assert (
        get_subscribe_url("fake-token")
        == "https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription&TopicArn=arn:aws:sns:us-east-1:1234567890:MediaConvertJobAlert&Token=fake-token"
    )
