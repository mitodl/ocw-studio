"""ocw_studio utilities"""
import hashlib
import hmac
import re
from enum import Flag, auto
from pathlib import Path
from typing import Tuple
from uuid import UUID, uuid4

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
    """
    return str(uuid4())


def is_valid_uuid(uuid_to_test: str, version: int=None) -> bool:
    """
    Returns True if the given string is a valid UUID
    """
    try:
        if version:
            uuid_obj = UUID(uuid_to_test, version=version)
        else:
            uuid_obj = UUID(uuid_to_test)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test


def get_file_extension(filepath: str) -> str:
    """
    Returns the extension for a given filepath

    Examples:
        get_file_extension("myfile.txt") == "txt"
        get_file_extension("myfile.tar.gz") == "tar.gz"
        get_file_extension("myfile") == ""
    """
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
    """
    return re.sub(r"^\/|\/$", "", filepath)


def are_equivalent_paths(filepath1: str, filepath2: str) -> bool:
    """Returns True if the two filepaths are equivalent"""
    return remove_trailing_slashes(filepath1) == remove_trailing_slashes(filepath2)


def get_dirpath_and_filename(
    filepath: str, expect_file_extension=True
) -> Tuple[str, str]:
    """
    Given a full filepath, returns the directory path and filename (without extension)

    Args:
        filepath (str): A full filepath
        expect_file_extension (bool): If True, the filepath is expected to have an extension. This
            flag is here to account for filenames that do not have extensions.

    Returns:
        (str, str): The dirpath and filename (without extension) of the filepath
    """
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
