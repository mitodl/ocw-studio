"""Tests for site config schema and validation"""
import os

import pytest
import yaml

from websites.config_schema.api import (
    validate_parsed_site_config,
    validate_raw_site_config,
)


SCHEMA_RESOURCES_DIR = "localdev/configs/"
SCHEMA_CONFIG_FILE = "ocw-course-site-config.yml"


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


def test_valid_config(site_config_yml):
    """The example site config should be valid"""
    validate_raw_site_config(site_config_yml)


def test_validate_parsed_site_config(mocker):
    """validate_parsed_site_config should dump a parsed site config as YAML and validate it"""
    patched_validate_raw = mocker.patch(
        "websites.config_schema.api.validate_raw_site_config"
    )
    parsed_config = {"parsed": "config"}
    raw_config = yaml.dump(parsed_config, Dumper=yaml.Dumper)
    validate_parsed_site_config(parsed_config)
    patched_validate_raw.assert_called_once_with(raw_config)


def test_invalid_key(parsed_site_config):
    """An invalid top-level key should cause a validation error"""
    config = parsed_site_config.copy()
    config["invalid_key"] = [1, 2, 3]
    with pytest.raises(ValueError):
        validate_parsed_site_config(config)


def test_exclusive_collection_keys(parsed_site_config):
    """A collection item defining more than one of a set of mutually-exclusive keys should cause a validation error"""
    config = parsed_site_config.copy()
    config["collections"][0] = {
        **config["collections"][0],
        "folder": "folder1",
        "files": [],
    }
    with pytest.raises(ValueError):
        validate_parsed_site_config(config)


def test_unique_names(parsed_site_config):
    """Every config item in a site config should have a unique name"""
    config = parsed_site_config.copy()
    config["collections"][1] = {
        **config["collections"][1],
        "name": config["collections"][0]["name"],
    }
    with pytest.raises(ValueError):
        validate_parsed_site_config(config)
    config = parsed_site_config.copy()
    # Find then index of a config item that defines a "files" list
    file_config_idx = next(
        i
        for i, config_item in enumerate(config["collections"])
        if "files" in config_item
    )
    # Set a "file" config item to have the same name as a top-level config item
    config["collections"][file_config_idx]["files"][0] = {
        **config["collections"][file_config_idx]["files"][0],
        "name": config["collections"][0]["name"],
    }
    with pytest.raises(ValueError):
        validate_parsed_site_config(config)
