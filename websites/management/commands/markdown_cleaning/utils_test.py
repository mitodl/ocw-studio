"""Tests for convert_baseurl_links_to_resource_links.py"""
from uuid import uuid4

import pytest

from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    patch_website_all,
    patch_website_contents_all,
    patch_website_starter_all,
)
from websites.management.commands.markdown_cleaning.utils import (
    CONTENT_FILENAME_MAX_LEN,
    ContentLookup,
    LegacyFileLookup,
    StarterSiteConfigLookup,
    UrlSiteRelativiser,
    get_rootrelative_url_from_content,
)


def string_uuid():
    return str(uuid4()).replace("-", "")


def get_content_lookup(contents):
    """Get a ContentLookup instance."""
    with patch_website_contents_all(contents), patch_website_all(
        {c.website for c in contents}
    ):
        return ContentLookup()


def test_get_rootrelative_url_from_content():
    c1 = WebsiteContentFactory.build(
        website=WebsiteFactory.build(url_path="courses/site-name-1"),
        dirpath="content/pages/path/to",
        filename="file1",
    )
    c2 = WebsiteContentFactory.build(
        website=WebsiteFactory.build(url_path="courses/site-name-2"),
        dirpath="content/pages/assignments",
        filename="_index",
    )
    c3 = WebsiteContentFactory.build(
        website=WebsiteFactory.build(url_path="courses/site-THREE"),
        dirpath="content/resources/long/path/to",
        filename="file3",
    )
    urls = [get_rootrelative_url_from_content(c) for c in [c1, c2, c3]]

    assert urls[0] == "/courses/site-name-1/pages/path/to/file1"
    assert urls[1] == "/courses/site-name-2/pages/assignments"
    assert urls[2] == "/courses/site-THREE/resources/long/path/to/file3"


def test_content_finder_is_site_specific():
    """Test that ContentLookup is site specific"""
    content_w1 = WebsiteContentFactory.build(
        website=WebsiteFactory.build(uuid="website-uuid-1"),
        dirpath="content/resources/path/to",
        filename="file1",
        text_id="content-uuid-1",
    )
    content_w2 = WebsiteContentFactory.build(
        website=WebsiteFactory.build(uuid="website-uuid-2"),
        dirpath="content/resources/path/to",
        filename="file1",
        text_id="content-uuid-1",
    )

    content_lookup = get_content_lookup([content_w1, content_w2])

    url = "/resources/path/to/file1"
    assert content_lookup.find_within_site(content_w1.website_id, url) == content_w1
    assert content_lookup.find_within_site(content_w2.website_id, url) == content_w2


@pytest.mark.parametrize(
    ("url", "content_relative_dirpath", "filename"),
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
        website=WebsiteFactory.build(uuid="website_uuid"),
        dirpath=f"content{content_relative_dirpath}",
        filename=filename,
        text_id="content-uuid",
    )

    content_lookup = get_content_lookup([content])

    assert content_lookup.find_within_site("website_uuid", url) == content


@pytest.mark.parametrize(
    ("root_relative_path", "base_site_name", "expected_content_uuid"),
    [
        ("/courses/pets/pages/animals/cats", None, "uuid-cats"),
        ("{{< baseurl >}}/pages/animals/cats", "pets", "uuid-cats"),
        ("/courses/pets/pages/animals/unicorns", None, "uuid-unicorns"),
        ("{{< baseurl >}}/pages/animals/unicorns", "pets", "uuid-unicorns"),
    ],
)
def test_content_finder_find(root_relative_path, base_site_name, expected_content_uuid):
    """Test finding content by url."""
    website = WebsiteFactory.build(name="pets")
    c1 = WebsiteContentFactory.build(
        filename="cats",
        dirpath="content/pages/animals",
        website=website,
        text_id="uuid-cats",
    )
    c2 = WebsiteContentFactory.build(
        filename="_index",
        dirpath="content/pages/animals/unicorns",
        website=website,
        text_id="uuid-unicorns",
    )

    content_lookup = get_content_lookup([c1, c2])
    base_site = website if base_site_name == website.name else None
    assert (
        content_lookup.find(root_relative_path, base_site).text_id
        == expected_content_uuid
    )


def test_content_finder_find_by_website_url_path_and_name():
    """Test finding content when website.url_path and website.name are different."""
    website = WebsiteFactory.build(name="pets", url_path="courses/animals")
    c1 = WebsiteContentFactory.build(
        filename="dogs",
        dirpath="content/pages",
        website=website,
        text_id="uuid-dogs",
    )
    content_lookup = get_content_lookup([c1])

    assert content_lookup.find("/courses/animals/pages/dogs").text_id == "uuid-dogs"
    assert content_lookup.find("/courses/pets/pages/dogs").text_id == "uuid-dogs"


@pytest.mark.parametrize(
    ("site_uuid", "content_index"), [("website_one", 0), ("website_two", 1)]
)
def test_content_finder_returns_metadata_for_site(site_uuid, content_index):
    contents = [
        WebsiteContentFactory.build(
            website=WebsiteFactory.build(uuid="website_one"),
            type="sitemetadata",
            text_id="content-1",
        ),
        WebsiteContentFactory.build(
            website=WebsiteFactory.build(uuid="website_two"),
            type="sitemetadata",
            text_id="content-2",
        ),
    ]

    content_lookup = get_content_lookup(contents)
    assert content_lookup.find_within_site(site_uuid, "/") == contents[content_index]


@patch_website_contents_all([])
def test_content_finder_raises_keyerror():
    content_lookup = get_content_lookup([])
    with pytest.raises(KeyError):
        assert content_lookup.find_within_site("website_uuid", "url/to/thing")


@pytest.mark.parametrize(
    ("url", "expected_index", "expected_relative_url"),
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
    with pytest.raises(ValueError, match="does not contain a website name"):
        get_site_relative_url("courses/my-favorite-course/thing")


@pytest.mark.parametrize(
    ("site_uuid", "legacy_site_relative_url", "expected_index"),
    [
        ("site-uuid-one", "/site/pages/someFileName.jpg", 0),
        ("site-uuid-one", "/site/pages/things/somefilename.jpg", 1),
        ("site-uuid-two", "/site/woofs/someFileName.jpg", 2),
    ],
)
def test_legacy_file_lookup(site_uuid, legacy_site_relative_url, expected_index):
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
        assert legacy_file_lookup.find(site_uuid, legacy_site_relative_url) == expected


def test_legacy_file_lookup_nonunique_filenames():
    website = WebsiteFactory.build(uuid="site-uuid-one")
    parent_a = WebsiteContentFactory.build(
        website=website,
        filename="alpha",
        dirpath="content/pages/parent",
    )
    parent_b = WebsiteContentFactory.build(
        website=website,
        filename="beta",
        dirpath="content/pages/parent",
    )
    c1a = WebsiteContentFactory.build(
        website=website,
        file=f"/courses/site_one/{string_uuid()}_some_file_name.jpg",
        text_id="content-uuid-1",
        parent=parent_a,
    )
    c1b = WebsiteContentFactory.build(
        website=website,
        file=f"/courses/site_one/{string_uuid()}_some_file_name.jpg",
        text_id="content-uuid-2",
        parent=parent_b,
    )
    contents = [c1a, c1b, parent_a, parent_b]
    with patch_website_contents_all(contents):
        legacy_file_lookup = LegacyFileLookup()

        unique_parent_url = "parent/alpha/some_file_name.jpg"
        duplicate_parent_url = "parent/some_file_name.jpg"
        assert legacy_file_lookup.find(website.uuid, unique_parent_url) == c1a
        with pytest.raises(legacy_file_lookup.MultipleMatchError):
            assert legacy_file_lookup.find(website.uuid, duplicate_parent_url)


@patch_website_contents_all([])
def test_legacy_file_lookup_raises_keyerror_for_none():
    legacy_file_lookup = LegacyFileLookup()
    with pytest.raises(KeyError):
        assert legacy_file_lookup.find("some-site-uuid", "captain-nemo.file")


def test_find_website_by_url_path():
    """Test finding a website by url_path."""
    contents = [
        WebsiteContentFactory.build(
            website=WebsiteFactory.build(url_path="courses/id", name="name"),
        )
    ]

    content_lookup = get_content_lookup(contents)
    assert content_lookup.find_website_by_url_path("courses/id").name == "name"


def test_site_config_lookup():
    """Test starter site config lookup returns correct config."""
    starter = WebsiteStarterFactory.build()

    with patch_website_starter_all([starter]):
        lookup = StarterSiteConfigLookup()
        assert lookup.get_config(starter.id).raw_data == starter.config
