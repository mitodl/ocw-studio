"""decorators for content_sync.backends"""

import functools
import logging
from collections.abc import Callable
from time import sleep
from typing import Any, Optional, TypeVar

from django.conf import settings
from django_redis import get_redis_connection
from github.GithubException import RateLimitExceededException

from content_sync.models import ContentSyncState

F = TypeVar("F", bound=Callable[..., Any])

log = logging.getLogger(__name__)


def retry_on_failure(func: F) -> F:
    """
    Retry a function a certain number of times if it fails.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retries = settings.CONTENT_SYNC_RETRIES
        while retries > 0:
            try:
                return func(*args, **kwargs)
            except RateLimitExceededException:  # noqa: PERF203
                # No point in retrying
                raise
            except:  # pylint:disable=bare-except  # noqa: E722
                retries = retries - 1
                if retries == 0:
                    raise
                sleep(1)
        return None

    return wrapper


def is_sync_enabled(func: Callable) -> Callable:
    """Returns True if the sync is enabled"""  # noqa: D401

    def wrapper(*args, **kwargs):
        if settings.CONTENT_SYNC_BACKEND:
            return func(*args, **kwargs)
        return None

    return wrapper


def is_publish_pipeline_enabled(func: Callable) -> Callable:
    """Returns True if the publishing pipeline is enabled"""  # noqa: D401

    def wrapper(*args, **kwargs):
        if settings.CONTENT_SYNC_PIPELINE_BACKEND:
            return func(*args, **kwargs)
        return None

    return wrapper


def check_sync_state(func: Callable) -> Callable:
    """
    Decorator that checks if a content_sync_state is synced before running a function,
    then marks it as synced as long as the function returns some non-falsy value.
    """  # noqa: D401

    def wrapper(self, sync_state: ContentSyncState):
        if not sync_state.is_synced:
            content = sync_state.content
            result = func(self, sync_state)
            if result:
                sync_state.synced_checksum = content.calculate_checksum()
                sync_state.save()
                return result
        return None

    return wrapper


def single_task(
    timeout: int, raise_block: Optional[bool] = True  # noqa: FBT002
) -> Callable:
    """
    Only allow one instance of a task to run concurrently, based on the task name
    and a first arg, if supplied (like Website.name).
    Based on https://bit.ly/2RO2aav
    """

    def task_run(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            has_lock = False
            client = get_redis_connection("redis")
            lock_id = f"{func.__name__}-id-{args[0] if args else 'single'}"
            lock = client.lock(lock_id, timeout=timeout)
            try:
                has_lock = lock.acquire(blocking=False)
                if has_lock:
                    return_value = func(*args, **kwargs)
                else:
                    if raise_block:
                        raise BlockingIOError
                    return_value = None
            finally:
                if has_lock and lock.locked():
                    lock.release()
            return return_value

        return wrapper

    return task_run
