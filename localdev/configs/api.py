"""Local development site config functionality"""
import json
import os
import re

import yaml
from django.conf import settings

from main.utils import get_file_extension


SOURCE_CONFIG_DIRECTORY = "localdev/configs"
JS_CONFIG_DIRECTORY = "static/js/resources"


def example_config_file_iter():
    """
    Iterates through all example site configs and yields some information about each filename/path

    Yields:
        (str, str, str): A tuple containing the directory path, filename without extension, and the extension for an
            example site config file
    """
    base_dir_path = os.path.join(settings.BASE_DIR, SOURCE_CONFIG_DIRECTORY)
    for dirpath, _, filenames in os.walk(base_dir_path):
        for filename in filenames:
            extension = get_file_extension(filename)
            if extension != "yml":
                continue
            base_filename = re.sub(r"\.{}$".format(extension), "", filename)
            yield dirpath, base_filename, extension


def generate_example_config_json(config_filepath):
    """
    Returns a site config serialized as a JSON string

    Args:
        config_filepath (str): The full path to a site config file

    Returns:
        str: The contents of the site config at the given filepath, serialized as a JSON string
    """
    with open(config_filepath) as f:
        raw_config = f.read().strip()
    parsed_config = yaml.load(raw_config, Loader=yaml.Loader)
    return json.dumps(parsed_config, sort_keys=True, indent=2)


def generate_example_configs():
    """
    Iterates through all example site configs in the codebase and generates equivalent files where they're needed.

    Returns:
        list(str): A list of files that were created/overwritten
    """
    written_files = []
    for dirpath, base_filename, extension in example_config_file_iter():
        filename = f"{base_filename}.{extension}"
        config_json = generate_example_config_json(os.path.join(dirpath, filename))
        json_filepath = os.path.join(JS_CONFIG_DIRECTORY, f"{base_filename}.json")
        with open(
            os.path.join(settings.BASE_DIR, json_filepath), "w+"
        ) as json_config_file:
            json_config_file.write(config_json)
        written_files.append(json_filepath)
    return written_files
