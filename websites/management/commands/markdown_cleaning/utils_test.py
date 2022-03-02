"""Tests for convert_baseurl_links_to_resource_links.py"""
from unittest.mock import patch
from uuid import uuid4

import pytest

from websites.management.commands.markdown_cleaning.utils import (
    ContentLookup,
    LegacyFileLookup,
    CONTENT_FILENAME_MAX_LEN,
    UrlSiteRelativiser
)
from websites.factories import WebsiteContentFactory, WebsiteFactory

@patch("websites.models.WebsiteContent.all_objects.all")
def test_content_finder_is_site_specific(mock):
    """Test that ContentLookup is site specific"""
    content_w1 = WebsiteContentFactory.build(
            website_id='website-uuid-1',
            dirpath="content/resources/path/to",
            filename="file1",
            text_id="content-uuid-1",
        )
    content_w2 = WebsiteContentFactory.build(
            website_id='website-uuid-2',
            dirpath="content/resources/path/to",
            filename="file1",
            text_id="content-uuid-1",
        )
    mock.return_value = [content_w1, content_w2]
    
    content_lookup = ContentLookup()

    url = '/resources/path/to/file1'
    assert content_lookup.find(content_w1.website_id, url) == content_w1
    assert content_lookup.find(content_w2.website_id, url) == content_w2

@pytest.mark.parametrize(
    ["url", "content_relative_dirpath", "filename"],
    [
        (
            # url is to an index file, not to dirpath/filename
            "/pages/pets/cat",
            "/pages/pets",
            "cat",
        ),
        (
            # url is to an index file, not to dirpath/filename
            "/pages/pets/cat/",
            "/pages/pets",
            "cat",
        ),
        (
            # url is to an index file, not to dirpath/filename
            "/pages/pets",
            "/pages/pets",
            "_index",
        ),
        # replaces periods with dashes 
        ("/pages/pets/c.a.t", "/pages/pets", "c-a-t"),
        # long filenames
        (
            "/pages/pets/" + "z" * CONTENT_FILENAME_MAX_LEN + "meowmeow",
            "/pages/pets",
            "z" * CONTENT_FILENAME_MAX_LEN,
        ),
    ],
)
@patch("websites.models.WebsiteContent.all_objects.all")
def test_content_finder_specific_url_replacements(
    mock, url, content_relative_dirpath, filename
):
    content = WebsiteContentFactory.build(
        website_id='website_uuid',
        dirpath=f"content{content_relative_dirpath}",
        filename=filename,
        text_id="content-uuid",
    )
    mock.return_value = [content]
    
    content_lookup = ContentLookup()

    assert content_lookup.find('website_uuid', url) == content

@pytest.mark.parametrize(
    ["site_uuid", "content_index"],
    [
        ("website_one", 0),
        ("website_two", 1)
    ]
)
@patch("websites.models.WebsiteContent.all_objects.all")
def test_content_finder_returns_metadata_for_site(mock, site_uuid, content_index):
    content = [
        WebsiteContentFactory.build(
            website_id='website_one',
            type='sitemetadata',
            text_id="content-1",
        ),
        WebsiteContentFactory.build(
            website_id='website_two',
            type='sitemetadata',
            text_id="content-2",
        )
    ]
    mock.return_value = content
    content_lookup = ContentLookup()
    assert content_lookup.find(site_uuid, '/') == content[content_index]

@patch("websites.models.WebsiteContent.all_objects.all")
def test_content_finder_raises_keyerror(mock):
    mock.return_value = []
    content_lookup = ContentLookup()
    with pytest.raises(KeyError):
        assert content_lookup.find('website_uuid', 'url/to/thing')

@pytest.mark.parametrize(
    ['url', 'expected_relative_url', 'expected_uuid'],
    [
        (
            '/courses/physics/theoretical/website_one/path/to/the/thing',
            '/path/to/the/thing',
            'uuid-one'
        ),
        (
            '/resources/website_two/a/really/cool/file.ext',
            '/a/really/cool/file.ext',
            'uuid-two'
        ),
        (
            '/resources/website_two/',
            '/',
            'uuid-two'
        ),
        (
            '/resources/website_two',
            '/',
            'uuid-two'
        ),
    ]
)
@patch("websites.models.Website.objects.all")
def test_url_site_relativiser(mock, url, expected_relative_url, expected_uuid):
    w1 = WebsiteFactory.build(name='website_one', uuid='uuid-one')
    w2 = WebsiteFactory.build(name='website_two', uuid='uuid-two')
    mock.return_value = [w1, w2]
    get_site_relative_url = UrlSiteRelativiser()

    assert get_site_relative_url(url) == (expected_uuid, expected_relative_url)

@patch("websites.models.Website.objects.all")
def test_url_site_relativiser_raises_value_errors(mock):
    mock.return_value = []
    get_site_relative_url = UrlSiteRelativiser()
    with pytest.raises(ValueError, match="does not contain a website name") as e:
        get_site_relative_url('courses/my-favorite-course/thing')

@pytest.mark.parametrize(
    ["site_uuid", "filename", "expected_index"],
    [
        ('site-uuid-one', 'someFileName.jpg', 0),
        ('site-uuid-one', 'somefilename.jpg', 1),
        ('site-uuid-two', 'someFileName.jpg', 2)
    ],
)
@patch("websites.models.WebsiteContent.all_objects.all")
def test_legacy_file_lookup(mock, site_uuid, filename, expected_index):
    uuid = lambda *args: str(uuid4()).replace('-', '')
    c1a = WebsiteContentFactory.build(
        website_id='site-uuid-one',
        file=f'/courses/site_one/{uuid()}_someFileName.jpg',
        text_id="content-uuid-1a",
    )
    c1b = WebsiteContentFactory.build(
        website_id='site-uuid-one',
        file=f'/courses/site_one/{uuid()}_somefilename.jpg',
        text_id="content-uuid-1b",
    )
    c2 = WebsiteContentFactory.build(
        website_id='site-uuid-two',
        file=f'/courses/site_two/{uuid()}_someFileName.jpg',
        text_id="content-uuid-two",
    )
    contents = [c1a, c1b, c2]
    expected = contents[expected_index]
    mock.return_value = contents
    legacy_file_lookup = LegacyFileLookup()
    assert legacy_file_lookup.find(site_uuid, filename) == expected