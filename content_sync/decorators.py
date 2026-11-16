"""decorators for content_sync.backends"""

import functools
import logging
from collections.abc import Callable
from time import sleep
from typing import TYPE_CHECKING, Any, TypeVar

from celery import Task
from django.conf import settings
from django_redis import get_redis_connection
from github.GithubException import RateLimitExceededException
from redis.exceptions import LockNotOwnedError

if TYPE_CHECKING:
    from content_sync.models import ContentSyncState

F = TypeVar("F", bound=Callable[..., Any])

log = logging.getLogger(__name__)


def retry_on_failure(func: F) -> F:  # noqa: UP047
    """
    Retry a function a certain number of times if it fails.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retries = settings.CONTENT_SYNC_RETRIES
        while retries > 0:
            try:
                return func(*args, **kwargs)
            except RateLimitExceededException:
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
    timeout: int,
    *,
    raise_block: bool | None = True,
    per_arg: bool = True,
) -> Callable:
    """
    Only allow one instance of a task to run concurrently, based on the task name
    and a first arg, if supplied (like Website.name). For a task declared with
    bind=True, the first arg is the one after the task instance.
    Based on https://bit.ly/2RO2aav

    Args:
        timeout(int): Seconds before the lock expires on its own
        raise_block(bool): Raise BlockingIOError if another instance holds the
            lock, rather than skip the call and return None
        per_arg(bool): Lock per value of the first arg. If False, take one lock
            for the task whatever its args.
    """

    def task_run(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            has_lock = False
            client = get_redis_connection("redis")
            # Celery passes a bound task its own instance first. Its repr has the
            # app's memory address, which differs between worker processes, so
            # it can't be part of a lock name that all workers share.
            lock_args = args[1:] if args and isinstance(args[0], Task) else args
            lock_key = lock_args[0] if per_arg and lock_args else "single"
            lock_id = f"{func.__name__}-id-{lock_key}"
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
                if has_lock:
                    try:
                        lock.release()
                    except LockNotOwnedError:
                        # The lock ran out mid-task, so it is gone or another
                        # worker holds it now. Leave it, and keep the result.
                        log.warning(
                            "single_task lock %s expired after %ss, before the task "
                            "finished",
                            lock_id,
                            timeout,
                        )
            return return_value

        return wrapper

    return task_run
