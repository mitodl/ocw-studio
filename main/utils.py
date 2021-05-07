"""ocw_studio utilities"""
import re
from enum import Flag, auto
from pathlib import Path
from uuid import uuid4


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
