"""Site config API tests"""
import os

import pytest
import yaml

from websites.constants import WEBSITE_CONFIG_CONTENT_DIR_KEY
from websites.site_config_api import (
    ConfigItem,
    config_item_iter,
    find_config_item,
    get_file_target,
    has_file_target,
    is_page_content,
)


SCHEMA_RESOURCES_DIR = "localdev/configs/"
SCHEMA_CONFIG_FILE = "basic-site-config.yml"

# pylint:disable=redefined-outer-name


@pytest.fixture()
def site_config_yml(settings):
    """Fixture that returns the contents of the example site config YAML file in the resource directory"""
    with open(
        os.path.join(settings.BASE_DIR, SCHEMA_RESOURCES_DIR, SCHEMA_CONFIG_FILE)
    ) as f:
        return f.read().strip()


@pytest.fixture()
def parsed_site_config(site_config_yml):
    """Fixture that returns the parsed contents of the example site config YAML file in the resource directory"""
    return yaml.load(site_config_yml, Loader=yaml.Loader)


def test_config_item_iter(parsed_site_config):
    """config_item_iter should yield each individual config item"""
    config_items = list(config_item_iter(parsed_site_config))
    assert len(config_items) == 4
    collections = parsed_site_config["collections"]
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


def test_find_config_item_repeatable(site_config_repeatable_only):
    """find_config_item should return a repeatable config item if one is found with the given name"""
    config_item = site_config_repeatable_only["collections"][0]
    assert (
        find_config_item(
            site_config_data=site_config_repeatable_only, name=config_item["name"]
        )
        == config_item
    )
    assert (
        find_config_item(
            site_config_data=site_config_repeatable_only, name="other-name-123"
        )
        is None
    )


def test_find_config_item_singleton(site_config_singleton_only):
    """find_config_item should return a singleton config item if one is found with the given name"""
    config_item = site_config_singleton_only["collections"][0]["files"][0]
    assert (
        find_config_item(
            site_config_data=site_config_singleton_only, name=config_item["name"]
        )
        == config_item
    )
    assert (
        find_config_item(
            site_config_data=site_config_singleton_only, name="other-name-123"
        )
        is None
    )


@pytest.mark.parametrize(
    "obj, exp_get_file_target, exp_has_file_target",
    [
        [{"folder": "abc/"}, "abc/", True],
        [{"file": "abc.txt"}, "abc.txt", True],
        [{"key": "value"}, None, False],
    ],
)
def test_file_target_utils(obj, exp_get_file_target, exp_has_file_target):
    """Util functions for dealing with folder/file target should return expected values"""
    assert get_file_target(obj) == exp_get_file_target
    assert has_file_target(obj) is exp_has_file_target


@pytest.mark.parametrize(
    "content_dir, folder_file_target, exp_result",
    [
        [None, "content", True],
        [None, "content/otherfolder", True],
        ["contentdir", "contentdir", True],
        ["contentdir", "contentdir/other", True],
        ["contentdir", "contentdir/file.txt", True],
        ["thisdir", "thatdir", False],
        ["thisdir", "thatdir/other", False],
    ],
)
def test_is_page_content(
    mocker, basic_site_config, content_dir, folder_file_target, exp_result
):
    """
    is_page_content should return True if the folder target of the repeatable config item starts with the
    content directory in the site config (or a default value)
    """
    config_item = basic_site_config["collections"][0].copy()
    patched_get_file_target = mocker.patch(
        "websites.site_config_api.get_file_target", return_value=folder_file_target
    )
    site_config = basic_site_config.copy()
    content_dir_config = (
        {} if content_dir is None else {WEBSITE_CONFIG_CONTENT_DIR_KEY: content_dir}
    )
    if WEBSITE_CONFIG_CONTENT_DIR_KEY in site_config:
        del site_config[WEBSITE_CONFIG_CONTENT_DIR_KEY]
    site_config = {**site_config, **content_dir_config}
    assert is_page_content(site_config, config_item) is exp_result
    patched_get_file_target.assert_called_once_with(config_item)
