"""Tests for site configs defined in localdev"""
import os

import yaml

from websites.config_schema.api import validate_parsed_site_config


LOCALDEV_OVERRIDE_CONFIG = "localdev/starters/site-config-override.yml"


def test_local_dev_configs(settings):
    """All site configs defined in the local override should be valid"""
    override_config_path = os.path.join(settings.BASE_DIR, LOCALDEV_OVERRIDE_CONFIG)
    with open(override_config_path) as f:
        raw_config_override = f.read().strip()
    parsed_config_override = yaml.load(raw_config_override, Loader=yaml.Loader)
    for _, site_config in parsed_config_override.items():
        validate_parsed_site_config(site_config)
