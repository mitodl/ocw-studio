""" Website models tests """
from urllib.parse import urljoin

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)


@pytest.mark.parametrize(
    "metadata, markdown, dirpath, exp_checksum",
    [
        [
            {"my": "metadata"},
            "# Markdown",
            None,
            "519b0f9225d269b6f2fe3636c8ef6d0de4c9fd8fde30990fb8a1c65c4575f3ae",
        ],
        [
            {"my": "metadata"},
            None,
            "path/to",
            "a6ffb383023705e862b9357c23155252808722a62a3effa7c0826a0918095a19",
        ],
        [
            None,
            "# Markdown",
            "path/to",
            "9323949f05768fb0a69ceb96eecb6bf040681fa17102fb93f33ee56493d8b41e",
        ],
    ],
)
def test_websitecontent_calculate_checksum(metadata, markdown, dirpath, exp_checksum):
    """ Verify calculate_checksum() returns the expected sha256 checksum """
    content = WebsiteContentFactory.build(
        markdown=markdown,
        metadata=metadata,
        dirpath=dirpath,
        filename="myfile",
        type="mytype",
        title="My Title",
    )
    # manually computed checksum in a python shell
    assert content.calculate_checksum() == exp_checksum


@pytest.mark.django_db
@pytest.mark.parametrize("has_file_widget", [True, False])
@pytest.mark.parametrize("has_file", [True, False])
def test_websitecontent_full_metadata(has_file_widget, has_file):
    """WebsiteContent.full_metadata returns expected file field in metadata when appropriate"""
    file = SimpleUploadedFile("test.txt", b"content")
    title = ("Test Title",)
    description = "Test Description"
    config_fields = [
        {"label": "Description", "name": "description", "widget": "text"},
        {"label": "My File", "name": "my_file", "widget": "file", "required": False},
    ]
    site_config = {
        "content-dir": "content",
        "collections": [
            {
                "name": "resource",
                "label": "Resource",
                "category": "Content",
                "folder": "content/resource",
                "fields": config_fields if has_file_widget else config_fields[0:1],
            }
        ],
    }
    starter = WebsiteStarterFactory.create(config=site_config)
    content = WebsiteContentFactory.build(
        type="resource",
        metadata={"title": title, "description": description},
        file=(file if has_file else None),
        website=WebsiteFactory(starter=starter),
    )

    if has_file_widget:
        assert content.full_metadata == {
            "title": title,
            "description": description,
            "my_file": content.file.url if has_file else None,
        }
    else:
        assert content.full_metadata == {"title": title, "description": description}


@pytest.mark.django_db
def test_website_starter_unpublished():
    """Website should set has_unpublished_live and has_unpublished_draft if the starter is updated"""
    website = WebsiteFactory.create(
        has_unpublished_live=False, has_unpublished_draft=False
    )
    second_website = WebsiteFactory.create(
        has_unpublished_live=False, has_unpublished_draft=False, starter=website.starter
    )
    website.starter.save()
    website.refresh_from_db()
    assert website.has_unpublished_draft is True
    assert website.has_unpublished_live is True
    second_website.refresh_from_db()
    assert second_website.has_unpublished_draft is True
    assert second_website.has_unpublished_live is True


@pytest.mark.django_db
def test_website_content_unpublished():
    """Website should set has_unpublished_live and has_unpublished_draft if any related content is updated"""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(website=website)
    website.has_unpublished_live = False
    website.has_unpublished_draft = False
    website.save()
    other_content = WebsiteContentFactory.create()
    other_content.save()
    website.refresh_from_db()
    # website should not have changed since the content is for a different website
    assert website.has_unpublished_live is False
    assert website.has_unpublished_draft is False
    content.save()
    website.refresh_from_db()
    assert website.has_unpublished_live is True
    assert website.has_unpublished_draft is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,root_url,is_home,version,expected_path",
    [
        ["test-course", "courses", False, "live", "courses/test-course"],
        ["ocw-home-page", "", True, "draft", ""],
    ],
)
def test_website_get_url(
    settings, name, root_url, is_home, version, expected_path
):  # pylint:disable=too-many-arguments
    """Verify that Website.get_full_url returns the expected value"""
    settings.OCW_STUDIO_LIVE_URL = "http://test-live.edu"
    settings.OCW_STUDIO_DRAFT_URL = "http://test-draft.edu"
    expected_domain = (
        settings.OCW_STUDIO_LIVE_URL
        if version == "live"
        else settings.OCW_STUDIO_DRAFT_URL
    )
    starter = WebsiteStarterFactory.create()
    starter.config["root-url-path"] = root_url
    starter.save()
    settings.ROOT_WEBSITE_NAME = name if is_home else "test-home"
    website = WebsiteFactory.create(name=name, starter=starter, url_path=expected_path)
    assert website.get_full_url(version) == urljoin(expected_domain, expected_path)


@pytest.mark.django_db
def test_website_get_url_no_starter():
    """Verify that Website.get_full_url returns None if there is no starter"""
    website = WebsiteFactory.create(starter=None)
    assert website.get_full_url("draft") is None
    assert website.get_full_url("live") is None
