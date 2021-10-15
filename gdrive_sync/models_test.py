"""Tests for gdrive_sync.models"""
import pytest

from gdrive_sync.factories import DriveFileFactory
from websites.factories import WebsiteFactory


@pytest.mark.django_db
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
    file_4 = DriveFileFactory.create(name="(file).PnG",  mime_type="image/png", s3_key=None)
    assert file_4.get_valid_s3_key() == f"{site_prefix}/{file_4.website.name}/file.png"
