"""Tests for decorators"""

import contextlib
from unittest.mock import ANY

import pytest
from celery import Celery

from content_sync import decorators
from content_sync.decorators import single_task
from external_resources.tasks import (
    submit_url_to_wayback_task,
    update_wayback_jobs_status_batch,
)
from gdrive_sync.tasks import import_website_files
from videos.tasks import update_youtube_statuses, update_youtube_tags_batch


@pytest.fixture
def celery_app():
    """Make a Celery app of its own, so test tasks stay out of the project's registry"""
    return Celery("decorators_test", set_as_current=False)


@pytest.fixture
def mock_redis(mocker):
    """Patch the Redis client that single_task takes its locks from"""
    return mocker.patch("content_sync.decorators.get_redis_connection").return_value


@pytest.mark.parametrize("has_lock", [False, True])
@pytest.mark.parametrize("raise_block", [False, True])
@pytest.mark.parametrize("input_arg", [None, "foo"])
def test_single_task(mocker, has_lock, raise_block, input_arg):
    """single_task should only allow 1 instance of inner task to run at same time"""
    mock_app = mocker.patch("content_sync.decorators.get_redis_connection")
    mock_app.return_value.lock.return_value.acquire.side_effect = [True, has_lock]

    func = mocker.Mock(__name__="testfunc")
    decorated_func = single_task(timeout=2, raise_block=raise_block)
    args = [input_arg] if input_arg else []
    decorated_func(func)(*args)
    if raise_block and not has_lock:
        with pytest.raises(BlockingIOError):
            decorated_func(func)(*args)
    else:
        decorated_func(func)(*args)
    mock_app.return_value.lock.assert_any_call(
        f"testfunc-id-{input_arg or 'single'}", timeout=2
    )
    assert func.call_count == (2 if has_lock else 1)


@pytest.mark.parametrize(
    ("args", "kwargs", "lock_name"),
    [
        (["site-a"], {}, "bound_task-id-site-a"),
        (["site-a"], {"user_pk": 1}, "bound_task-id-site-a"),
        (["site-b"], {}, "bound_task-id-site-b"),
        ([], {"name": "site-a"}, "bound_task-id-single"),
        ([], {}, "bound_task-id-single"),
    ],
)
def test_single_task_bound_task_lock_name(
    mock_redis, celery_app, args, kwargs, lock_name
):
    """A bound task should lock on its first arg after self, not on the task object"""
    mock_redis.lock.return_value.acquire.return_value = True

    @celery_app.task(bind=True)
    @single_task(timeout=2)
    def bound_task(self, name=None, user_pk=None):
        return "ran"

    assert bound_task.apply(args, kwargs).get() == "ran"
    mock_redis.lock.assert_called_once_with(lock_name, timeout=2)


def test_single_task_bound_task_blocks_same_arg_only(celery_app):
    """A held lock should block a bound task for the same arg and no other"""

    @celery_app.task(bind=True)
    @single_task(timeout=10)
    def bound_task(self, name):
        return name

    held = decorators.get_redis_connection("redis").lock(
        "bound_task-id-site-a", timeout=10
    )
    assert held.acquire(blocking=False)
    try:
        with pytest.raises(BlockingIOError):
            bound_task.run("site-a")
        assert bound_task.run("site-b") == "site-b"
    finally:
        held.release()


def test_single_task_releases_lock(mocker):
    """single_task should free its lock once the task returns"""
    mock_log = mocker.patch("content_sync.decorators.log")

    @single_task(timeout=10)
    def quick_task(name):
        return name

    assert quick_task("site-a") == "site-a"
    lock = decorators.get_redis_connection("redis").lock(
        "quick_task-id-site-a", timeout=10
    )
    assert lock.acquire(blocking=False)
    lock.release()
    mock_log.warning.assert_not_called()


@pytest.mark.parametrize("taken_over", [False, True])
def test_single_task_lock_expired_before_task_finished(mocker, taken_over):
    """A lock that ran out mid-task should not fail the task or free another holder"""
    mock_log = mocker.patch("content_sync.decorators.log")
    other = decorators.get_redis_connection("redis").lock(
        "slow_task-id-site-a", timeout=10
    )

    @single_task(timeout=10)
    def slow_task(name):
        # The lock runs out, and maybe another worker takes it
        other.redis.delete(other.name)
        if taken_over:
            assert other.acquire(blocking=False)
        return name

    try:
        assert slow_task("site-a") == "site-a"
        assert other.owned() is taken_over
    finally:
        if taken_over:
            other.release()
    mock_log.warning.assert_called_once()


def test_single_task_lock_expired_keeps_task_error(mocker):
    """An error from the task should not be replaced by a failed lock release"""
    mocker.patch("content_sync.decorators.log")
    other = decorators.get_redis_connection("redis").lock(
        "failing_task-id-site-a", timeout=10
    )

    @single_task(timeout=10)
    def failing_task(name):
        other.redis.delete(other.name)
        assert other.acquire(blocking=False)
        raise ValueError(name)

    try:
        with pytest.raises(ValueError, match="site-a"):
            failing_task("site-a")
    finally:
        other.release()


@pytest.mark.parametrize("bind", [False, True])
@pytest.mark.parametrize("args", [[], ["site-a"], ["site-b", 1]])
def test_single_task_per_arg_false(mock_redis, celery_app, bind, args):
    """per_arg=False should take one lock for the task whatever its args"""
    mock_redis.lock.return_value.acquire.return_value = True

    @celery_app.task(bind=bind)
    @single_task(timeout=2, per_arg=False)
    def whole_task(*_args):
        return "ran"

    assert whole_task.apply(args).get() == "ran"
    mock_redis.lock.assert_called_once_with("whole_task-id-single", timeout=2)


@pytest.mark.parametrize(
    ("task", "args", "kwargs", "lock_name"),
    [
        pytest.param(
            import_website_files,
            ["site-a"],
            {"user_pk": 1},
            "import_website_files-id-site-a",
            id="import_website_files-per-site",
        ),
        pytest.param(
            update_youtube_statuses,
            [],
            {},
            "update_youtube_statuses-id-single",
            id="update_youtube_statuses-task-wide",
        ),
        pytest.param(
            submit_url_to_wayback_task,
            [111],
            {},
            "submit_url_to_wayback_task-id-single",
            id="submit_url_to_wayback_task-task-wide",
        ),
        pytest.param(
            update_wayback_jobs_status_batch,
            [["job-1"]],
            {},
            "update_wayback_jobs_status_batch-id-single",
            id="update_wayback_jobs_status_batch-task-wide",
        ),
        pytest.param(
            update_wayback_jobs_status_batch,
            [],
            {"job_ids": ["job-1"]},
            "update_wayback_jobs_status_batch-id-single",
            id="update_wayback_jobs_status_batch-job-ids-kwarg",
        ),
        pytest.param(
            update_youtube_tags_batch,
            [["yt-1", "yt-2"]],
            {"add_course_tag": True},
            "update_youtube_tags_batch-id-single",
            id="update_youtube_tags_batch-task-wide",
        ),
    ],
)
def test_single_task_lock_names_of_bound_tasks(
    mock_redis, task, args, kwargs, lock_name
):
    """Each bound task should lock per site or task-wide, as it was meant to"""
    mock_redis.lock.return_value.acquire.return_value = False
    with contextlib.suppress(BlockingIOError):
        task.run(*args, **kwargs)
    mock_redis.lock.assert_called_once_with(lock_name, timeout=ANY)
