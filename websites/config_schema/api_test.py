"""Tests for site config schema and validation"""
import os

import pytest
import yaml

from websites.config_schema.api import (
    validate_parsed_site_config,
    validate_raw_site_config,
)


SCHEMA_RESOURCES_DIR = "websites/config_schema/resources"
SCHEMA_CONFIG_FILE = "valid-config.yml"


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


@pytest.mark.parametrize(
    "collection_dict",
    [
        {"folder": "folder1", "file": "file1.txt"},
        {"folder": "folder1", "files": []},
        {"file": "file1.txt", "files": []},
    ],
)
def test_exclusive_collection_keys(parsed_site_config, collection_dict):
    """A collection item defining more than one of a set of mutually-exclusive keys should cause a validation error"""
    config = parsed_site_config.copy()
    config["collections"][0] = {**config["collections"][0], **collection_dict}
    with pytest.raises(ValueError):
        validate_parsed_site_config(config)
