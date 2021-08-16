"""Tests for schema validators"""
import yaml

from websites.config_schema.validators import CollectionsKeysRule


def _validate(validation_class, data):
    """
    Validate a starter config
    """
    if isinstance(data, str):
        data = yaml.load(data, Loader=yaml.SafeLoader)
    return validation_class.apply_rule(data)


def test_no_file_or_folder():
    """either file or folder must be present in the schema"""
    data = """
    {
  "collections": [
    {
    }
  ],
  "root-url-path": "/"
}
    """
    assert _validate(CollectionsKeysRule, data) == [
        "collections.0: A collection must have one of the following keys: files, folder"
    ]
