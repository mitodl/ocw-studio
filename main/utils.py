"""ocw_studio utilities"""
from enum import Flag, auto
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
