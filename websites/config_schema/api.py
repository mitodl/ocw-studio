"""API for parsing/validating site configs"""
import os
import json

import yamale
from yamale.yamale_error import YamaleError
import yaml
from django.conf import settings

from websites.config_schema.validators import (
    CollectionsKeysRule,
    ContentFolderRule,
    MenuOnlyRule,
    RequiredTitleRule,
    UniqueNamesRule,
)


SITE_CONFIG_SCHEMA_PATH = os.path.join(
    settings.BASE_DIR, "websites/config_schema/site-config-schema.yml"
)

# Any additional validation rules for the site config schema (beyond what the schema itself already defines)
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
    """
    schema = yamale.make_schema(path=SITE_CONFIG_SCHEMA_PATH)
    yamale_data = yamale.make_data(content=yaml_to_validate)
    print("this is running")
    try:
        yamale.validate(schema, yamale_data)
        # Retrieve the parsed YAML (Yamale returns a list of lists instead of just the parsed YAML)
        parsed_data = yamale_data[0][0]
        # Schema is valid according to the YAML document. Now apply our custom rules...
        for added_schema_rule in ADDED_SCHEMA_RULES:
            added_schema_rule.validate(parsed_data, schema_path=SITE_CONFIG_SCHEMA_PATH)
    except YamaleError as e:
        print('Validation failed!\n')
        for result in e.results:
            print("Error validating data with '%s'\n\t" % (result.schema))
            deduped_split_errors = [ error.split(":") for error in list(set(result.errors))]

            # this dict maps an error path to an array of all the errors that we found at that path
            # this lets us print *once* the error context and then print all the error messages about it
            unique_error_paths = {}
            for [k, v] in deduped_split_errors:
                if k in unique_error_paths:
                    unique_error_paths[k].append(v.strip())
                else:
                    unique_error_paths[k] = [v.strip()]

            for path, errors in unique_error_paths.items():
                error_path = list(map(
                    lambda key : int(key) if key.isnumeric() else key,
                    path.strip().split(".")
                ))

                def fetch_data(obj, path):
                    key, *rest = path

                    if isinstance(obj, list):
                        if key < len(obj):
                            if len(rest) > 0:
                                return fetch_data(obj[key], rest)
                            else:
                                return obj[key]
                        else:
                            return obj
                    else:
                        if key in obj:
                            if len(rest) > 0:
                                return fetch_data(obj[key], rest)
                            else:
                                return obj[key]
                        else:
                            return obj

                error_context = fetch_data(
                    yamale_data[0][0],
                    error_path[:-1]
                )
                formatted_errors = "\n".join([f"\t{error}" for error in errors])
                formatted_context = "\n".join([
                    f"\t{line}" for line in 
                    json.dumps(
                    error_context,
                    indent=4
                ).split("\n")
                ])

                print(f"Found errors:\n{formatted_errors}")
                print(f"At path:\n\t{path}")
                print(f"In context:\n{formatted_context}\n")
        exit(1)

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
    """
    raw_site_config = yaml.dump(config_to_validate, Dumper=yaml.Dumper)
    return validate_raw_site_config(raw_site_config)
