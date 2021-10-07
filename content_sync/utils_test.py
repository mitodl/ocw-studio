"""Content sync utility functionality tests"""
import pytest

from content_sync.utils import get_destination_filepath, get_destination_url
from websites.factories import WebsiteContentFactory, WebsiteStarterFactory
from websites.site_config_api import ConfigItem, SiteConfig


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "has_missing_name, is_bad_config_item",
    [
        [True, False],
        [False, True],
    ],
)
def test_get_destination_filepath_errors(mocker, has_missing_name, is_bad_config_item):
    """
    get_destination_filepath should log an error and return None if the site config is missing the given name, or if
    the config item does not have a properly configured destination.
    """
    patched_log = mocker.patch("content_sync.utils.log")
    # From basic-site-config.yml
    config_item_name = "blog"
    if is_bad_config_item:
        mocker.patch.object(
            SiteConfig,
            "find_item_by_name",
            return_value=ConfigItem(
                item={"name": config_item_name, "poorly": "configured"}
            ),
        )
    starter = WebsiteStarterFactory.build()
    content = WebsiteContentFactory.build(
        is_page_content=False,
        type="non-existent-config-name" if has_missing_name else config_item_name,
    )
    return_value = get_destination_filepath(
        content=content, site_config=SiteConfig(starter.config)
    )
    patched_log.error.assert_called_once()
    assert return_value is None


def test_get_destination_url_errors(mocker):
    """
    get_destination_url should log an error if it is called with a a WebsiteContent object without
    is_page_content set to true
    """
    patched_log = mocker.patch("content_sync.utils.log")
    # From basic-site-config.yml
    config_item_name = "blog"
    starter = WebsiteStarterFactory.build()
    content = WebsiteContentFactory.build(
        is_page_content=False,
        type=config_item_name,
    )
    return_value = get_destination_url(
        content=content, site_config=SiteConfig(starter.config)
    )
    patched_log.error.assert_called_once()
    assert return_value is None


@pytest.mark.parametrize(
    "is_page_content, dirpath, filename, expected",
    [
        [True, "content/pages", "_index", "/pages/"],
        [True, "content/pages", "hx_network", "/pages/hx_network"],
        [
            True,
            "content/pages/lecture-notes",
            "java_3d_lecture",
            "/pages/lecture-notes/java_3d_lecture",
        ],
        [True, "content/resources", "image", "/resources/image"],
        [False, "", "", None],
    ],
)
def test_get_destination_url(is_page_content, dirpath, filename, expected):
    """get_destination_url should create a url for a piece of content"""
    content = WebsiteContentFactory.create(
        is_page_content=is_page_content, dirpath=dirpath, filename=filename
    )
    assert (
        get_destination_url(content, SiteConfig(content.website.starter.config))
        == expected
    )


@pytest.mark.parametrize(
    "is_page_content, dirpath, filename, expected",
    [
        [True, "content/pages", "_index", "content/pages/_index.md"],
        [True, "content/pages", "hx_network", "content/pages/hx_network.md"],
        [
            True,
            "content/pages/lecture-notes",
            "java_3d_lecture",
            "content/pages/lecture-notes/java_3d_lecture.md",
        ],
        [True, "content/resources", "image", "content/resources/image.md"],
        [False, "", "", None],
        [False, "config/_default/menus.yaml", "menus.yaml", None],
    ],
)
def test_get_destination_filepath(is_page_content, dirpath, filename, expected):
    """get_destination_filepath should create the filepath for a piece of content"""
    content = WebsiteContentFactory.create(
        is_page_content=is_page_content, dirpath=dirpath, filename=filename
    )
    assert (
        get_destination_filepath(content, SiteConfig(content.website.starter.config))
        == expected
    )
