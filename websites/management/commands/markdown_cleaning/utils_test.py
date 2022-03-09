"""Tests for convert_baseurl_links_to_resource_links.py"""
from uuid import uuid4

import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.testing_utils import (
    patch_website_all,
    patch_website_contents_all,
)
from websites.management.commands.markdown_cleaning.utils import (
    CONTENT_FILENAME_MAX_LEN,
    ContentLookup,
    LegacyFileLookup,
    UrlSiteRelativiser,
)


def string_uuid():
    return str(uuid4()).replace("-", "")


def test_content_finder_is_site_specific():
    """Test that ContentLookup is site specific"""
    content_w1 = WebsiteContentFactory.build(
        website_id="website-uuid-1",
        dirpath="content/resources/path/to",
        filename="file1",
        text_id="content-uuid-1",
    )
    content_w2 = WebsiteContentFactory.build(
        website_id="website-uuid-2",
        dirpath="content/resources/path/to",
        filename="file1",
        text_id="content-uuid-1",
    )

    with patch_website_contents_all([content_w1, content_w2]):
        content_lookup = ContentLookup()

        url = "/resources/path/to/file1"
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
def test_content_finder_specific_url_replacements(
    url, content_relative_dirpath, filename
):
    content = WebsiteContentFactory.build(
        website_id="website_uuid",
        dirpath=f"content{content_relative_dirpath}",
        filename=filename,
        text_id="content-uuid",
    )

    with patch_website_contents_all([content]):
        content_lookup = ContentLookup()

        assert content_lookup.find("website_uuid", url) == content


@pytest.mark.parametrize(
    ["site_uuid", "content_index"], [("website_one", 0), ("website_two", 1)]
)
def test_content_finder_returns_metadata_for_site(site_uuid, content_index):
    contents = [
        WebsiteContentFactory.build(
            website_id="website_one",
            type="sitemetadata",
            text_id="content-1",
        ),
        WebsiteContentFactory.build(
            website_id="website_two",
            type="sitemetadata",
            text_id="content-2",
        ),
    ]
    with patch_website_contents_all(contents):
        content_lookup = ContentLookup()
        assert content_lookup.find(site_uuid, "/") == contents[content_index]


@patch_website_contents_all([])
def test_content_finder_raises_keyerror():
    content_lookup = ContentLookup()
    with pytest.raises(KeyError):
        assert content_lookup.find("website_uuid", "url/to/thing")


@pytest.mark.parametrize(
    ["url", "expected_index", "expected_relative_url"],
    [
        (
            "/courses/physics/theoretical/website_zero/path/to/the/thing",
            0,
            "/path/to/the/thing",
        ),
        (
            "/courses/physics/theoretical/website_zero/path/to/the/thing#my-fragment",
            0,
            "/path/to/the/thing#my-fragment",
        ),
        ("/resources/website_one/a/really/cool/file.ext", 1, "/a/really/cool/file.ext"),
        (
            "/resources/website_one/",
            1,
            "/",
        ),
        (
            "/resources/website_one",
            1,
            "/",
        ),
    ],
)
def test_url_site_relativiser(url, expected_index, expected_relative_url):
    w1 = WebsiteFactory.build(name="website_zero")
    w2 = WebsiteFactory.build(name="website_one")
    sites = [w1, w2]
    with patch_website_all(sites):
        get_site_relative_url = UrlSiteRelativiser()

        assert get_site_relative_url(url) == (
            sites[expected_index],
            expected_relative_url,
        )


@patch_website_all([])
def test_url_site_relativiser_raises_value_errors():
    get_site_relative_url = UrlSiteRelativiser()
    with pytest.raises(ValueError, match="does not contain a website name") as e:
        get_site_relative_url("courses/my-favorite-course/thing")


@pytest.mark.parametrize(
    ["site_uuid", "filename", "expected_index"],
    [
        ("site-uuid-one", "someFileName.jpg", 0),
        ("site-uuid-one", "somefilename.jpg", 1),
        ("site-uuid-two", "someFileName.jpg", 2),
    ],
)
def test_legacy_file_lookup(site_uuid, filename, expected_index):
    c1a = WebsiteContentFactory.build(
        website_id="site-uuid-one",
        file=f"/courses/site_one/{string_uuid()}_someFileName.jpg",
        text_id="content-uuid-1a",
    )
    c1b = WebsiteContentFactory.build(
        website_id="site-uuid-one",
        file=f"/courses/site_one/{string_uuid()}_somefilename.jpg",
        text_id="content-uuid-1b",
    )
    c2 = WebsiteContentFactory.build(
        website_id="site-uuid-two",
        file=f"/courses/site_two/{string_uuid()}_someFileName.jpg",
        text_id="content-uuid-two",
    )
    contents = [c1a, c1b, c2]
    expected = contents[expected_index]
    with patch_website_contents_all(contents):
        legacy_file_lookup = LegacyFileLookup()
        assert legacy_file_lookup.find(site_uuid, filename) == expected


def test_legacy_file_lookup_raises_nonunique_for_multiple_matches():
    c1a = WebsiteContentFactory.build(
        website_id="site-uuid-one",
        file=f"/courses/site_one/{string_uuid()}_some_file_name.jpg",
        text_id="content-uuid-1",
    )
    c1b = WebsiteContentFactory.build(
        website_id="site-uuid-one",
        file=f"/courses/site_one/{string_uuid()}_some_file_name.jpg",
        text_id="content-uuid-2",
    )
    contents = [c1a, c1b]
    with patch_website_contents_all(contents):
        legacy_file_lookup = LegacyFileLookup()
        with pytest.raises(legacy_file_lookup.MultipleMatchError):
            assert legacy_file_lookup.find("site-uuid-one", "some_file_name.jpg")


@patch_website_contents_all([])
def test_legacy_file_lookup_raises_keyerror_for_none():
    legacy_file_lookup = LegacyFileLookup()
    with pytest.raises(KeyError):
        assert legacy_file_lookup.find("some-site-uuid", "captain-nemo.file")
