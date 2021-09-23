"""decorators for gdrive_sync """
from typing import Callable

from django.conf import settings


def is_gdrive_enabled(func: Callable) -> Callable:
    """ Returns True if the gdrive sync is enabled """

    def wrapper(*args, **kwargs):
        if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
            return func(*args, **kwargs)
        return None

    return wrapper
