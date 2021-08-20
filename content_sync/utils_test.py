"""Content sync utility functionality tests"""
import pytest

from content_sync.utils import get_destination_filepath
from websites.factories import WebsiteContentFactory, WebsiteStarterFactory
from websites.site_config_api import ConfigItem, SiteConfig


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
    return_value = get_destination_filepath(
        content=content, site_config=SiteConfig(starter.config)
    )
    patched_log.error.assert_called_once()
    assert return_value is None
