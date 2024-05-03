"""API for parsing/validating site configs"""

import os

import yamale
import yaml
from django.conf import settings

from websites.config_schema.validators import (
    CollectionsKeysRule,
    ContentFolderRule,
    MenuOnlyRule,
    RequiredTitleRule,
    UniqueNamesRule,
)

SITE_CONFIG_SCHEMA_PATH = os.path.join(  # noqa: PTH118
    settings.BASE_DIR, "websites/config_schema/site-config-schema.yml"
)

# Any additional validation rules for the site config schema (beyond what the schema itself already defines)  # noqa: E501
# should be added here.
ADDED_SCHEMA_RULES = [
    CollectionsKeysRule,
    UniqueNamesRule,
    ContentFolderRule,
    RequiredTitleRule,
    MenuOnlyRule,
]


def validate_raw_site_config(yaml_to_validate):
    """
    Validates the given site config YAML contents against our schema and any additional custom rules

    Args:
        yaml_to_validate (str): Site config YAML contents to validate against our schema

    Returns:
        None

    Raises:
        ValueError: Raised if the given site config YAML is invalid
    """  # noqa: D401, E501
    schema = yamale.make_schema(path=SITE_CONFIG_SCHEMA_PATH)
    yamale_data = yamale.make_data(content=yaml_to_validate)
    yamale.validate(schema, yamale_data)
    # Retrieve the parsed YAML (Yamale returns a list of lists instead of just the parsed YAML)  # noqa: E501
    parsed_data = yamale_data[0][0]
    # Schema is valid according to the YAML document. Now apply our custom rules...
    for added_schema_rule in ADDED_SCHEMA_RULES:
        added_schema_rule.validate(parsed_data, schema_path=SITE_CONFIG_SCHEMA_PATH)


def validate_parsed_site_config(config_to_validate):
    """
    Validates the given parsed site config (*not* the raw YAML contents) against our schema and
    any additional custom rules

    Args:
        config_to_validate (any): Parsed site config YAML contents to validate against our schema

    Returns:
        None

    Raises:
        ValueError: Raised if the given site config YAML is invalid
    """  # noqa: D401, E501
    raw_site_config = yaml.dump(config_to_validate, Dumper=yaml.Dumper)
    return validate_raw_site_config(raw_site_config)
