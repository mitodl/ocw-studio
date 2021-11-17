"""decorators for content_sync.backends"""
import functools
import logging
from time import sleep
from typing import Callable

from django.conf import settings
from github.GithubException import RateLimitExceededException

from content_sync.models import ContentSyncState
from main.celery import app


log = logging.getLogger(__name__)


def retry_on_failure(func: Callable) -> Callable:
    """
    Retry a function a certain number of times if it fails.
    """

    def wrapper(*args, **kwargs):
        retries = settings.CONTENT_SYNC_RETRIES
        while retries > 0:
            try:
                return func(*args, **kwargs)
            except RateLimitExceededException:
                # No point in retrying
                raise
            except:  # pylint:disable=bare-except
                retries = retries - 1
                if retries == 0:
                    raise
                sleep(1)

    return wrapper


def is_sync_enabled(func: Callable) -> Callable:
    """ Returns True if the sync is enabled """

    def wrapper(*args, **kwargs):
        if settings.CONTENT_SYNC_BACKEND:
            return func(*args, **kwargs)
        return None

    return wrapper


def is_publish_pipeline_enabled(func: Callable) -> Callable:
    """ Returns True if the publishing pipeline is enabled """

    def wrapper(*args, **kwargs):
        if settings.CONTENT_SYNC_PIPELINE:
            return func(*args, **kwargs)
        return None

    return wrapper


def check_sync_state(func: Callable) -> Callable:
    """
    Decorator that checks if a content_sync_state is synced before running a function,
    then marks it as synced as long as the function returns some non-falsy value.
    """

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


def single_website_task(timeout: int) -> Callable:
    """
    Only allow one instance of a website task to run concurrently.
    Assumes first arg is the website name.
    Based on https://bit.ly/2RO2aav
    """

    def task_run(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            has_lock = False
            lock_id = f"{func.__name__}-website-{args[0]}"
            lock = app.backend.client.lock(lock_id, timeout=timeout)

            try:
                has_lock = lock.acquire(blocking=False)
                if has_lock:
                    return_value = func(*args, **kwargs)
                else:
                    raise BlockingIOError()
            finally:
                if has_lock and lock.locked():
                    lock.release()
            return return_value

        return wrapper

    return task_run
