"""Tests for local development site configs"""
import json
import os

import yaml

from localdev.configs.api import JS_CONFIG_DIRECTORY, example_config_file_iter
from websites.config_schema.api import validate_parsed_site_config


def test_valid_local_dev_configs():
    """All site configs defined in the local override should be valid"""
    total_example_configs = 0
    for dirpath, base_filename, extension in example_config_file_iter():
        with open(os.path.join(dirpath, f"{base_filename}.{extension}")) as f:
            raw_config_override = f.read().strip()
        parsed_site_config = yaml.load(raw_config_override, Loader=yaml.Loader)
        validate_parsed_site_config(parsed_site_config)
        total_example_configs += 1
    assert total_example_configs >= 1


def test_equivalent_example_configs(settings):
    """
    There should be an equivalent JSON config file available in the frontend for every example config file in this
    codebase
    """
    _assert_msg = (
        "Please use the 'generate_example_configs' management command to ensure that example config files match the "
        "source of truth."
    )
    for dirpath, base_filename, extension in example_config_file_iter():
        filename = f"{base_filename}.{extension}"
        with open(os.path.join(dirpath, filename)) as f:
            raw_yaml_config = f.read().strip()
        parsed_config = yaml.load(raw_yaml_config, Loader=yaml.Loader)
        #
        js_config_path = os.path.join(
            settings.BASE_DIR, JS_CONFIG_DIRECTORY, f"{base_filename}.json"
        )
        assert (
            os.path.exists(js_config_path) is True
        ), f"'{js_config_path}' does not exist. {_assert_msg}"
        with open(js_config_path) as f:
            raw_json_config = f.read().strip()
        assert (
            json.dumps(parsed_config, sort_keys=True, indent=2) == raw_json_config
        ), f"'{js_config_path}' does not match the contents of '{filename}'. {_assert_msg}"
