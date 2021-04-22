"""Site config API tests"""
import os

import pytest
import yaml

from websites.site_config_api import ConfigItem, config_item_iter


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
