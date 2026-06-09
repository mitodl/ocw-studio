"""Tests for the remove_uuid_from_filenames management command."""  # noqa: INP001

import pytest
from django.core.management import call_command

from gdrive_sync.factories import DriveFileFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


UUID_PREFIX = "ab3d029952cda060f4afcd811189a591"


@pytest.fixture
def mock_s3(mocker):
    """Mock S3 client used by the command."""
    return mocker.patch(
        "websites.management.commands.remove_uuid_from_filenames.get_boto3_client"
    )


def test_renames_file_with_uuid_prefix(settings, mock_s3):
    """Files whose basename starts with a 32-char hex UUID prefix are renamed in S3 and in the DB."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_document.pdf"
    content = WebsiteContentFactory.create(website=website, file=old_key)
    expected_new_key = f"sites/{website.name}/document.pdf"

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3_client = mock_s3.return_value
    mock_s3_client.copy_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/{old_key}",
        Key=expected_new_key,
        ACL="public-read",
    )
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=old_key,
    )
    content.refresh_from_db()
    assert str(content.file) == expected_new_key


def test_also_updates_drive_file(settings, mock_s3):
    """The associated DriveFile.s3_key is updated when it matches the old S3 key."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    content = WebsiteContentFactory.create(website=website, file=old_key)
    drive_file = DriveFileFactory.create(
        resource=content, website=website, s3_key=old_key
    )
    expected_new_key = f"sites/{website.name}/photo.jpg"

    call_command("remove_uuid_from_filenames", filter=website.name)

    drive_file.refresh_from_db()
    assert drive_file.s3_key == expected_new_key


def test_skips_file_without_uuid_prefix(mock_s3):
    """Files whose basename does not start with a UUID prefix are left unchanged."""
    website = WebsiteFactory.create()
    plain_key = f"sites/{website.name}/document.pdf"
    content = WebsiteContentFactory.create(website=website, file=plain_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()
    content.refresh_from_db()
    assert str(content.file) == plain_key


def test_skips_conflicting_target_key(mock_s3):
    """A file is skipped when the target key is already used by another WebsiteContent."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_notes.txt"
    new_key = f"sites/{website.name}/notes.txt"
    WebsiteContentFactory.create(website=website, file=old_key)
    WebsiteContentFactory.create(website=website, file=new_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()


def test_dry_run_makes_no_changes(mock_s3):
    """With --dry-run, no S3 operations are performed and the DB is not modified."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_slides.pptx"
    content = WebsiteContentFactory.create(website=website, file=old_key)

    call_command("remove_uuid_from_filenames", filter=website.name, dry_run=True)

    mock_s3.return_value.copy_object.assert_not_called()
    mock_s3.return_value.delete_object.assert_not_called()
    content.refresh_from_db()
    assert str(content.file) == old_key


def test_filter_limits_to_specified_website(mock_s3):
    """The --filter argument restricts processing to the named website only."""
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    key_a = f"sites/{website_a.name}/{UUID_PREFIX}_file.pdf"
    key_b = f"sites/{website_b.name}/{UUID_PREFIX}_file.pdf"
    content_a = WebsiteContentFactory.create(website=website_a, file=key_a)
    content_b = WebsiteContentFactory.create(website=website_b, file=key_b)

    call_command("remove_uuid_from_filenames", filter=website_a.name)

    assert mock_s3.return_value.copy_object.call_count == 1
    content_a.refresh_from_db()
    assert str(content_a.file) == f"sites/{website_a.name}/file.pdf"
    content_b.refresh_from_db()
    assert str(content_b.file) == key_b


def test_s3_error_is_reported_and_does_not_abort(mock_s3):
    """An S3 error on one file is reported and processing continues for other files."""
    website = WebsiteFactory.create()
    failing_key = f"sites/{website.name}/{UUID_PREFIX}_bad.pdf"
    good_uuid = "cc4d029952cda060f4afcd811189a591"
    succeeding_key = f"sites/{website.name}/{good_uuid}_good.pdf"
    failing_content = WebsiteContentFactory.create(website=website, file=failing_key)
    succeeding_content = WebsiteContentFactory.create(
        website=website, file=succeeding_key
    )

    mock_s3.return_value.copy_object.side_effect = [
        Exception("S3 unavailable"),
        None,
    ]

    call_command("remove_uuid_from_filenames", filter=website.name)

    assert mock_s3.return_value.copy_object.call_count == 2
    failing_content.refresh_from_db()
    assert str(failing_content.file) == failing_key
    succeeding_content.refresh_from_db()
    assert str(succeeding_content.file) == f"sites/{website.name}/good.pdf"
