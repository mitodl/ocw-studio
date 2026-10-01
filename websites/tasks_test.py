"""Tests for websites Celery tasks."""

import pytest
from celery.exceptions import Retry
from github.GithubException import RateLimitExceededException

from websites import tasks
from websites.factories import WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_rate_limit_check(settings):
    """Turn the check off, since a local .env can turn it on and build a real backend."""
    settings.GITHUB_RATE_LIMIT_CHECK = False


@pytest.fixture
def mock_sync(mocker):
    """Mock the per-site sync function the task calls in-process."""
    return mocker.patch("websites.tasks.sync_website_content")


def test_syncs_each_website_in_turn(mock_sync):
    """Each run syncs one website and queues the rest."""
    first, second = WebsiteFactory.create_batch(2)

    tasks.sync_renamed_websites.delay([first.name, second.name])

    assert [call.args[0] for call in mock_sync.call_args_list] == [
        first.name,
        second.name,
    ]


def test_a_low_rate_limit_requeues_with_a_capped_countdown(mocker, mock_sync):
    """A wait past the visibility timeout would get the task redelivered."""
    website = WebsiteFactory.create()
    mocker.patch("websites.tasks._git_rate_limit_wait", return_value=3600)
    requeue = mocker.patch("websites.tasks.sync_renamed_websites.apply_async")

    tasks.sync_renamed_websites([website.name])

    mock_sync.assert_not_called()
    requeue.assert_called_once_with(([website.name],), countdown=1800)


def test_a_held_lock_retries_the_site_a_minute_later(mocker, mock_sync):
    """An editor's sync holds the per-site lock, so try the same site again."""
    first, second = WebsiteFactory.create_batch(2)
    mock_sync.side_effect = BlockingIOError
    requeue = mocker.patch("websites.tasks.sync_renamed_websites.apply_async")

    tasks.sync_renamed_websites([first.name, second.name])

    requeue.assert_called_once_with(([first.name, second.name],), countdown=60)


def test_a_rate_limit_hit_mid_sync_requeues_the_site(mocker, mock_sync):
    """The reset time cannot be read after the fact, so wait the capped time."""
    website = WebsiteFactory.create()
    mock_sync.side_effect = RateLimitExceededException(403, {}, {})
    requeue = mocker.patch("websites.tasks.sync_renamed_websites.apply_async")

    tasks.sync_renamed_websites([website.name])

    requeue.assert_called_once_with(([website.name],), countdown=1800)


def test_a_failing_site_is_logged_and_the_rest_continue(mock_sync, caplog):
    """One bad site must not stop the others."""
    first, second = WebsiteFactory.create_batch(2)
    mock_sync.side_effect = [OSError("github is unhappy"), None]

    tasks.sync_renamed_websites.delay([first.name, second.name])

    assert mock_sync.call_count == 2
    assert first.name in caplog.text


def test_sync_leaves_publish_status_alone(mock_sync):
    """Unlike sync_unsynced_websites, nothing resets live or draft status."""
    website = WebsiteFactory.create(
        live_publish_status="succeeded", latest_build_id_live=7
    )

    tasks.sync_renamed_websites.delay([website.name])

    website.refresh_from_db()
    assert website.live_publish_status == "succeeded"
    assert website.latest_build_id_live == 7


def test_rate_limit_wait_is_zero_without_the_check(mocker):
    """No backend is even built when rate limiting is off."""
    get_backend = mocker.patch("websites.tasks.api.get_sync_backend")

    assert tasks._git_rate_limit_wait(WebsiteFactory.create()) == 0  # noqa: SLF001
    get_backend.assert_not_called()


def test_rate_limit_wait_counts_down_to_the_reset(settings, mocker):
    """A low remaining count waits until the reset time GitHub reports."""
    settings.GITHUB_RATE_LIMIT_CHECK = True
    settings.GITHUB_RATE_LIMIT_CUTOFF = 100
    backend = mocker.Mock(spec=tasks.GithubBackend)
    backend.api = mocker.Mock()
    backend.api.git.rate_limiting = (10, 5000)
    backend.api.git.rate_limiting_resettime = 1_000_900
    mocker.patch("websites.tasks.api.get_sync_backend", return_value=backend)
    mocker.patch("websites.tasks.time.time", return_value=1_000_000)

    assert tasks._git_rate_limit_wait(WebsiteFactory.create()) == 900  # noqa: SLF001


def test_rate_limit_wait_has_a_floor(settings, mocker):
    """A reset time already past must not requeue the task every second."""
    settings.GITHUB_RATE_LIMIT_CHECK = True
    backend = mocker.Mock(spec=tasks.GithubBackend)
    backend.api = mocker.Mock()
    backend.api.git.rate_limiting = (10, 5000)
    backend.api.git.rate_limiting_resettime = 999_000
    mocker.patch("websites.tasks.api.get_sync_backend", return_value=backend)
    mocker.patch("websites.tasks.time.time", return_value=1_000_000)

    assert tasks._git_rate_limit_wait(WebsiteFactory.create()) == 60  # noqa: SLF001


@pytest.fixture
def eager_retries(monkeypatch):
    """Let eager tasks retry. With propagation on, Celery raises Retry instead."""
    # The namespaced name, since it takes precedence over task_eager_propagates.
    monkeypatch.setattr(tasks.app.conf, "CELERY_TASK_EAGER_PROPAGATES", False)


@pytest.mark.usefixtures("eager_retries")
def test_an_incomplete_chunk_is_run_again(mocker):
    """A reference left unpatched is only fixed by running the chunk again."""
    run_chunk = mocker.patch(
        "websites.tasks.uuid_renames.run_chunk",
        side_effect=[{"incomplete": True}, {"incomplete": False}],
    )

    result = tasks.rename_uuid_files_chunk.delay(0, [], [], [])

    assert run_chunk.call_count == 2
    assert result.get() == {"incomplete": False}


@pytest.mark.usefixtures("eager_retries")
def test_a_chunk_stops_retrying_and_reports(mocker):
    """After the last retry the summary is returned, so the callback still runs."""
    run_chunk = mocker.patch(
        "websites.tasks.uuid_renames.run_chunk", return_value={"incomplete": True}
    )

    result = tasks.rename_uuid_files_chunk.delay(0, [], [], [])

    assert run_chunk.call_count == tasks.CHUNK_MAX_RETRIES + 1
    assert result.get() == {"incomplete": True}


@pytest.mark.parametrize(
    "task",
    [
        tasks.rename_uuid_files,
        tasks.rename_uuid_files_chunk,
        tasks.finish_uuid_rename,
        tasks.sync_renamed_websites,
    ],
)
def test_tasks_survive_a_lost_worker(task):
    """Without reject_on_worker_lost a killed worker's task is acknowledged and lost."""
    assert task.acks_late is True
    assert task.reject_on_worker_lost is True


def test_tasks_run_on_the_batch_queue():
    """They share the batch queue with mass publishes, not the default one."""
    from main.celery import app  # noqa: PLC0415

    for name in (
        "rename_uuid_files",
        "rename_uuid_files_chunk",
        "finish_uuid_rename",
        "sync_renamed_websites",
    ):
        assert app.conf.task_routes[f"websites.tasks.{name}"] == {"queue": "batch"}


def test_chunk_retries_wait_longer_each_time(mocker):
    """1, 2, then 4 minutes, so a short database outage can pass."""
    mocker.patch(
        "websites.tasks.uuid_renames.run_chunk", return_value={"incomplete": True}
    )
    task = tasks.rename_uuid_files_chunk
    retry = mocker.patch.object(task, "retry", side_effect=Retry())

    for retries, countdown in ((0, 60), (1, 120), (2, 240)):
        task.push_request(retries=retries)
        try:
            with pytest.raises(Retry):
                task.run(0, [], [], [])
        finally:
            task.pop_request()
        assert retry.call_args.kwargs["countdown"] == countdown
