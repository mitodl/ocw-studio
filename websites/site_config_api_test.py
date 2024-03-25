"""Site config API tests"""

import pytest

from websites.constants import (
    WEBSITE_CONFIG_CONTENT_DIR_KEY,
    WEBSITE_CONFIG_DEFAULT_CONTENT_DIR,
)
from websites.models import WebsiteContent
from websites.site_config_api import ConfigItem, SiteConfig

# pylint:disable=redefined-outer-name


@pytest.mark.parametrize(
    ("raw_config_item", "exp_file_target", "exp_has_file_target"),
    [
        [{"folder": "abc/"}, "abc/", True],  # noqa: PT007
        [{"file": "abc.txt"}, "abc.txt", True],  # noqa: PT007
        [{"key": "value"}, None, False],  # noqa: PT007
    ],
)
def test_config_item_file_target(raw_config_item, exp_file_target, exp_has_file_target):
    """Util functions for dealing with folder/file target should return expected values"""
    config_item = ConfigItem(item=raw_config_item)
    assert config_item.file_target == exp_file_target
    assert config_item.has_file_target() == exp_has_file_target


def test_config_item_name():
    """ConfigItem.name should return the 'name' value"""
    name = "config-item-name"
    config_item = ConfigItem(item={"name": name})
    assert config_item.name == name


@pytest.mark.parametrize(
    ("raw_config_item", "exp_is_folder", "exp_is_file"),
    [
        [{"folder": "abc/"}, True, False],  # noqa: PT007
        [{"file": "abc.txt"}, False, True],  # noqa: PT007
        [{"key": "value"}, False, False],  # noqa: PT007
    ],
)
def test_config_item_is_folder_file(raw_config_item, exp_is_folder, exp_is_file):
    """ConfigItem.is_folder_item/is_file_item should return expected values"""
    config_item = ConfigItem(item=raw_config_item)
    assert config_item.is_folder_item() == exp_is_folder
    assert config_item.is_file_item() == exp_is_file


def test_site_config_iter_items(basic_site_config):
    """SiteConfig.iter_items should yield each individual config item"""
    site_config = SiteConfig(basic_site_config)
    config_items = list(site_config.iter_items())
    assert len(config_items) == 5
    collections = basic_site_config["collections"]
    assert config_items[0] == ConfigItem(
        item=collections[0], parent_item=None, path="collections.0"
    )
    assert config_items[1] == ConfigItem(
        item=collections[1], parent_item=None, path="collections.1"
    )
    assert config_items[2] == ConfigItem(
        item=collections[2], parent_item=None, path="collections.2"
    )
    assert config_items[3] == ConfigItem(
        item=collections[2]["files"][0],
        parent_item=collections[2],
        path="collections.2.files.0",
    )


@pytest.mark.parametrize(
    ("content_dir_value", "exp_result"),
    [
        ["mycontentdir", "mycontentdir"],  # noqa: PT007
        [None, WEBSITE_CONFIG_DEFAULT_CONTENT_DIR],  # noqa: PT007
    ],
)
def test_content_dir(basic_site_config, content_dir_value, exp_result):
    """SiteConfig.content_dir should return the content dir value or a default if it doesn't exist"""
    updated_site_config = basic_site_config.copy()
    if content_dir_value is None:
        del updated_site_config[WEBSITE_CONFIG_CONTENT_DIR_KEY]
    else:
        updated_site_config[WEBSITE_CONFIG_CONTENT_DIR_KEY] = content_dir_value
    site_config = SiteConfig(updated_site_config)
    assert site_config.content_dir == exp_result


def test_find_config_item_name_repeatable(basic_site_config):
    """SiteConfig.find_item_by_name should return a repeatable config item if one is found with the given name"""
    site_config = SiteConfig(basic_site_config)
    config_item = next(
        item for item in site_config.iter_items() if item.is_folder_item()
    )
    assert config_item is not None
    assert site_config.find_item_by_name(config_item.name) == config_item
    assert site_config.find_item_by_name("other-name-123") is None


def test_find_config_item_name_singleton(basic_site_config):
    """SiteConfig.find_item_by_name should return a singleton config item if one is found with the given name"""
    site_config = SiteConfig(basic_site_config)
    config_item = next(item for item in site_config.iter_items() if item.is_file_item())
    assert config_item is not None
    assert site_config.find_item_by_name(config_item.name) == config_item
    assert site_config.find_item_by_name("other-name-123") is None


def test_find_config_item_by_filepath(basic_site_config):
    """SiteConfig.find_item_by_filepath should return a config item if one is found with the given filepath"""
    site_config = SiteConfig(basic_site_config)
    all_config_items = list(site_config.iter_items())
    assert (
        site_config.find_item_by_filepath("data/metadata.json") == all_config_items[3]
    )
    assert site_config.find_item_by_filepath("bad/path") is None


@pytest.mark.parametrize(
    ("content_dir", "folder_file_target", "exp_result"),
    [
        [None, "content", True],  # noqa: PT007
        [None, "content/otherfolder", True],  # noqa: PT007
        ["contentdir", "contentdir", True],  # noqa: PT007
        ["contentdir", "contentdir/other", True],  # noqa: PT007
        ["contentdir", "contentdir/file.txt", True],  # noqa: PT007
        ["thisdir", "thatdir", False],  # noqa: PT007
        ["thisdir", "thatdir/other", False],  # noqa: PT007
    ],
)
def test_is_page_content(
    basic_site_config, content_dir, folder_file_target, exp_result
):
    """
    SiteConfig.is_page_content should return True if the folder target of the repeatable config item starts with the
    content directory in the site config (or a default value)
    """
    site_config = SiteConfig(basic_site_config)
    site_config.raw_data[WEBSITE_CONFIG_CONTENT_DIR_KEY] = content_dir
    config_item = next(
        item for item in site_config.iter_items() if item.is_folder_item()
    )
    config_item.item["folder"] = folder_file_target
    assert site_config.is_page_content(config_item) is exp_result


@pytest.mark.parametrize(
    ("content_type", "field_name"),
    [["resource", "image"], ["blog", None]],  # noqa: PT007
)
def test_find_file_field(basic_site_config, content_type, field_name):
    """The expected file field should be returned if any"""
    site_config = SiteConfig(basic_site_config)
    config_item = next(
        (item for item in site_config.iter_items() if item.name == content_type), None
    )
    file_field = site_config.find_file_field(config_item)
    if field_name:
        assert file_field["name"] == "image"
    else:
        assert file_field is None


@pytest.mark.parametrize("cls", [None, WebsiteContent])
@pytest.mark.parametrize("resource_type", [None, "Image"])
@pytest.mark.parametrize("file_type", [None, "image/png"])
@pytest.mark.parametrize("use_defaults", [True, False])
@pytest.mark.parametrize("values", [True, False])
def test_generate_item_metadata(  # pylint: disable=too-many-arguments  # noqa: PLR0913
    parsed_site_config, cls, resource_type, file_type, use_defaults, values
):
    """generate_item_metadata should return the expected dict"""
    class_data = {} if cls else {"title": "", "file": ""}
    default_license = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
    expected_data = {
        "description": "",
        "resourcetype": (resource_type or "") if values else "",
        "file_type": (file_type or "") if values else "",
        "learning_resource_types": [],
        "license": default_license if use_defaults else "",
        "image_metadata": {"image-alt": "", "caption": "", "credit": ""},
        "video_metadata": {"youtube_id": "", "video_speakers": "", "video_tags": ""},
        "video_files": {
            "video_thumbnail_file": "",
            "video_captions_file": "",
            "video_transcript_file": "",
        },
        **class_data,
    }
    site_config = SiteConfig(parsed_site_config)
    values = {"resourcetype": resource_type, "file_type": file_type} if values else {}
    assert (
        site_config.generate_item_metadata(
            "resource", cls, use_defaults=use_defaults, values=values
        )
        == expected_data
    )
