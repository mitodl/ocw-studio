"""Tests for gdrive_sync.models"""
import pytest

from gdrive_sync.conftest import (
    all_starters_items_fields,
    generate_related_content_data,
)
from gdrive_sync.factories import DriveFileFactory
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.factories import WebsiteContentFactory, WebsiteFactory


@pytest.mark.django_db()
def test_get_valid_s3_key():
    """get_valid_s3_key avoids dupe s3 keys"""
    site = WebsiteFactory.create()
    site_prefix = site.starter.config.get("root-url-path").rstrip("/")
    file_1 = DriveFileFactory.create(
        name="(file).PnG", website=site, mime_type="image/png", s3_key=None
    )
    file_1.s3_key = file_1.get_valid_s3_key()
    assert file_1.s3_key == f"{site_prefix}/{site.name}/file.png"
    file_1.save()
    file_2 = DriveFileFactory.create(
        name="File!.pNG", website=site, mime_type="image/png", s3_key=None
    )
    file_2.s3_key = file_2.get_valid_s3_key()
    assert file_2.s3_key == f"{site_prefix}/{site.name}/file2.png"
    file_2.save()
    file_3 = DriveFileFactory.create(
        name="FILE?.png", website=site, mime_type="image/png", s3_key=None
    )
    file_3.s3_key = file_3.get_valid_s3_key()
    assert file_3.s3_key == f"{site_prefix}/{site.name}/file3.png"
    # Different website
    file_4 = DriveFileFactory.create(
        name="(file).PnG", mime_type="image/png", s3_key=None
    )
    assert file_4.get_valid_s3_key() == f"{site_prefix}/{file_4.website.name}/file.png"
    # Unicode filename
    file_5 = DriveFileFactory.create(
        name="テストファイル.png", website=site, mime_type="image/png", s3_key=None
    )
    file_5.s3_key = file_5.get_valid_s3_key()
    assert file_5.s3_key == f"{site_prefix}/{site.name}/テストファイル.png"


@pytest.mark.django_db()
def test_get_content_dependencies():
    """get_content_dependencies should return content that uses `drive_file.resource`."""
    for starter, item, field in all_starters_items_fields():
        website = WebsiteFactory.create()
        resource = WebsiteContentFactory.create(
            type=CONTENT_TYPE_RESOURCE,
            website=website,
        )
        drive_file = DriveFileFactory.create(website=website, resource=resource)

        content_data = generate_related_content_data(
            starter,
            field,
            resource.text_id,
            website,
        )
        if content_data:
            content = WebsiteContentFactory.create(
                **content_data,
                type=item.name,
                website=website,
            )

        dependencies = drive_file.get_content_dependencies()

        if content_data:
            assert len(dependencies) != 0
            assert dependencies[0] == content
        else:
            assert len(dependencies) == 0


@pytest.mark.django_db()
def test_drivefile_allows_large_files():
    """
    Ensure database column can store large file sizes, e.g., bigger than int4.
    """
    fifty_GB = 5e10
    DriveFileFactory.create(size=fifty_GB)
