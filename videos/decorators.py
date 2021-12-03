""" decorators for videos """
from typing import Callable

from django.conf import settings


def is_threeplay_enabled(func: Callable) -> Callable:
    """ Returns True if threeplay is enabled """

    def wrapper(*args, **kwargs):
        if settings.THREEPLAY_API_KEY and settings.THREEPLAY_PROJECT_ID:
            return func(*args, **kwargs)
        return None

    return wrapper
