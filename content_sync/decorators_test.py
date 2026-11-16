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
