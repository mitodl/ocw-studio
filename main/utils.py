"""ocw_studio utilities"""

import hashlib
import hmac
import re
from enum import Flag, auto
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from django.conf import settings
from django.db.models.fields.json import KeyTextTransform
from django.http import HttpRequest


class FeatureFlag(Flag):
    """
    FeatureFlag enum

    Members should have values of increasing powers of 2 (1, 2, 4, 8, ...)

    """

    EXAMPLE_FEATURE = auto()


def uuid_string():
    """
    Generates a v4 UUID and casts it as a string

    Returns:
        str: UUID cast as a string
    """  # noqa: D401
    return str(uuid4())


def is_valid_uuid(uuid_to_test: str) -> bool:
    """
    Returns True if the given string is a valid UUID
    """  # noqa: D401
    try:
        UUID(uuid_to_test)
        return True  # noqa: TRY300
    except ValueError:
        return False


def get_file_extension(filepath: str) -> str:
    """
    Returns the extension for a given filepath

    Examples:
        get_file_extension("myfile.txt") == "txt"
        get_file_extension("myfile.tar.gz") == "tar.gz"
        get_file_extension("myfile") == ""
    """  # noqa: D401
    extension_with_dot = "".join(Path(filepath).suffixes).lower()
    if extension_with_dot:
        return extension_with_dot[1:]
    return ""


def remove_trailing_slashes(filepath: str) -> str:
    """
    Removes trailing slashes from a directory path or full filepath

    Examples:
        remove_trailing_slashes("/my/path/") == "my/path"
        remove_trailing_slashes("my/path/") == "my/path"
        remove_trailing_slashes("/path/to/myfile.pdf") == "path/to/myfile.pdf"
    """  # noqa: D401
    return re.sub(r"^\/|\/$", "", filepath)


def are_equivalent_paths(filepath1: str, filepath2: str) -> bool:
    """Returns True if the two filepaths are equivalent"""  # noqa: D401
    return remove_trailing_slashes(filepath1) == remove_trailing_slashes(filepath2)


def get_dirpath_and_filename(
    filepath: str, expect_file_extension=True  # noqa: FBT002
) -> tuple[str, str]:
    """
    Given a full filepath, returns the directory path and filename (without extension)

    Args:
        filepath (str): A full filepath
        expect_file_extension (bool): If True, the filepath is expected to have an extension. This
            flag is here to account for filenames that do not have extensions.

    Returns:
        (str, str): The dirpath and filename (without extension) of the filepath
    """  # noqa: E501
    path_obj = Path(filepath)
    path_parts = [part for part in path_obj.parts if part != "/"]
    if not path_obj.suffix and expect_file_extension:
        filename = ""
    else:
        filename = (
            path_obj.name
            if not path_obj.suffix
            else path_obj.name[: -len(path_obj.suffix)]
        )
        path_parts = path_parts[0 : (len(path_parts) - 1)]
    return ("/".join(path_parts), filename or None)


def valid_key(key: str, request: HttpRequest) -> bool:
    """
    Determine if the signature sent in a request is valid
    """
    digest = hmac.new(key.encode("utf-8"), request.body, hashlib.sha1).hexdigest()
    sig_parts = request.headers["X-Hub-Signature"].split("=", 1)
    return hmac.compare_digest(sig_parts[1], digest)


def truncate_words(content: str, length: int, suffix: Optional[str] = "...") -> str:
    """Truncate text to < length chars, keeping words intact"""
    if len(content) <= length:
        return content
    else:
        return content[: (length - len(suffix))].rsplit(" ", 1)[0] + suffix


class NestableKeyTextTransform:
    """
    From https://stackoverflow.com/questions/65921227/how-to-use-keytexttransform-for-nested-json
    Returns a KeyTextTransform for nested JSON fields

    Args:
        field (str): the top level field
        path (str*): any amount of nested fields to dig down

    Returns:
        (KeyTextTransform): A KeyTextTransform for the nested value
    """

    def __new__(cls, field, *path):
        """Create a new NestableKeyTextTransform object"""
        if not path:
            msg = "Path must contain at least one key."
            raise ValueError(msg)
        head, *tail = path
        field = KeyTextTransform(head, field)
        for head in tail:
            field = KeyTextTransform(head, field)
        return field


def is_dev() -> bool:
    """
    Returns True or False if settings.ENVIRONMENT is set to "dev"

    Returns:
        (bool): A boolean indicating whether on not the environment is dev
    """  # noqa: D401
    return settings.ENVIRONMENT == "dev"


def get_dict_list_item_by_field(items: list[dict], field: str, value: str):
    """
    Iterates a list of dicts and returns the first item where the value of the field matches the passed in value

    Args:
        items (list[dict]): A list of dicts to iterate through
        field (str): A string representing the field to check
        value (str): The value of the given field to match on

    Returns:
        (dict): The first dict with a field value that matches the given parameters
    """  # noqa: E501, D401
    return next(
        (item for item in items if item.get(field, None) == value),
        None,
    )


def get_base_filename(filename: str) -> str:
    """Return base filename without appended extension"""
    return filename.rsplit("_", 1)[0]
