"""Project conftest"""

import os
from types import SimpleNamespace

import pytest
import yaml
from django.db.models.signals import pre_save
from django.test import override_settings

from content_sync import decorators
from fixtures.common import *  # pylint:disable=wildcard-import,unused-wildcard-import  # noqa: F403
from websites.constants import OMNIBUS_STARTER_SLUG
from websites.models import WebsiteContent, WebsiteStarter
from websites.signals import update_navmenu_on_page_url_change
from websites.site_config_api import SiteConfig


@pytest.fixture(autouse=True)
def default_settings(settings):
    """Set default settings for all tests"""
    settings.DISABLE_WEBPACK_LOADER_STATS = True


@pytest.fixture(autouse=True)
def mock_gdrive_build(mocker):
    """
    Prevent tests from making real HTTP calls to the Google API discovery endpoint.
    googleapiclient.discovery.build() fetches a discovery document over the network
    when first called. Tests that exercise gdrive or YouTube code paths should mock
    at the service/task level; this fixture ensures the underlying HTTP call is never
    made by any test that doesn't explicitly need it.
    """
    mocker.patch("gdrive_sync.api.build")
    mocker.patch("videos.youtube.build")


@pytest.fixture(autouse=True)
def no_retry_sleep(mocker):
    """
    Skip the one-second pause between @retry_on_failure attempts. Retries still
    happen, so call counts are unchanged; a test that cares about the pause can
    patch content_sync.decorators.sleep itself.
    """
    mocker.patch("content_sync.decorators.sleep")


@pytest.fixture(scope="session", autouse=True)
def isolated_media_root(tmp_path_factory):
    """
    Give each test session its own MEDIA_ROOT. Under pytest-xdist every worker
    restarts the factory sequences, so two workers can build the same upload
    path and race on it in a shared directory.
    """
    with override_settings(MEDIA_ROOT=str(tmp_path_factory.mktemp("media"))):
        yield


class _WorkerScopedRedis:
    """Redis client proxy that namespaces lock names with the xdist worker id"""

    def __init__(self, client, worker_id):
        self._client = client
        self._worker_id = worker_id

    def lock(self, name, *args, **kwargs):
        """Take the lock under a name only this worker uses"""
        return self._client.lock(f"{self._worker_id}:{name}", *args, **kwargs)

    def __getattr__(self, attr):
        return getattr(self._client, attr)


@pytest.fixture(scope="session", autouse=True)
def isolated_task_locks():
    """
    Keep pytest-xdist workers from contending for @single_task locks. Lock
    names come from the task name and first argument, such as "single", a pk
    or a website name, and those repeat across workers that share one Redis.
    A worker that loses the race skips the task or raises BlockingIOError.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker_id:
        yield
        return
    get_connection = decorators.get_redis_connection
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            decorators,
            "get_redis_connection",
            lambda alias: _WorkerScopedRedis(get_connection(alias), worker_id),
        )
        yield


@pytest.fixture
def mocked_celery(mocker):
    """Mock object that patches certain celery functions"""
    exception_class = TabError
    replace_mock = mocker.patch(
        "celery.app.task.Task.replace", autospec=True, side_effect=exception_class
    )
    group_mock = mocker.patch("celery.group", autospec=True)
    chain_mock = mocker.patch("celery.chain", autospec=True)

    return SimpleNamespace(
        replace=replace_mock,
        group=group_mock,
        chain=chain_mock,
        replace_exception_class=exception_class,
    )


@pytest.fixture
def course_starter(settings, db):  # noqa: ARG001
    """Returns the 'course'-type WebsiteStarter that is seeded in a data migration"""  # noqa: D401
    return WebsiteStarter.objects.get(slug=settings.OCW_COURSE_STARTER_SLUG)


@pytest.fixture
def omnibus_starter(db):  # noqa: ARG001
    """Returns the omnibus WebsiteStarter that is seeded in a data migration"""  # noqa: D401
    return WebsiteStarter.objects.get(slug=OMNIBUS_STARTER_SLUG)


@pytest.fixture
def omnibus_config(settings, db):  # noqa: ARG001
    """Returns the omnibus site config"""  # noqa: D401
    with open(  # noqa: PTH123
        os.path.join(  # noqa: PTH118
            settings.BASE_DIR, "localdev/configs/omnibus-site-config.yml"
        )
    ) as f:
        raw_config = f.read().strip()
    parsed_config = yaml.load(raw_config, Loader=yaml.SafeLoader)
    return SiteConfig(parsed_config)


@pytest.fixture
def ocw_course_config(settings):
    """Returns the parsed OCW course site config.

    WebsiteStarterFactory's default config has no relation widgets, so tests
    that care about relation fields build a starter from this instead.
    """  # noqa: D401
    with open(  # noqa: PTH123
        os.path.join(  # noqa: PTH118
            settings.BASE_DIR, "localdev/configs/ocw-course-site-config.yml"
        )
    ) as f:
        return yaml.load(f.read().strip(), Loader=yaml.SafeLoader)


def pytest_addoption(parser):
    """Pytest hook that adds command line parameters"""
    parser.addoption(
        "--simple",
        action="store_true",
        help="Run tests only (no cov, warning output silenced)",
    )


def pytest_configure(config):
    """Pytest hook to perform some initial configuration"""
    if getattr(config.option, "simple") is True:  # noqa: B009
        # NOTE: These plugins are already configured by the time the pytest_cmdline_main
        #       hook is run, so we can't simply add/alter the command line options in
        #       that hook. This hook is being used to reconfigure/unregister plugins
        #       that we can't change via the pytest_cmdline_main hook.  Switch off
        #       coverage plugin
        cov = config.pluginmanager.get_plugin("_cov")
        cov.options.no_cov = True
        # Remove warnings plugin to suppress warnings
        if config.pluginmanager.has_plugin("warnings"):
            warnings_plugin = config.pluginmanager.get_plugin("warnings")
            config.pluginmanager.unregister(warnings_plugin)


@pytest.fixture(autouse=True)
def disable_websitecontent_signal():
    """Disable page url update signal"""

    # Disconnect
    pre_save.disconnect(update_navmenu_on_page_url_change, sender=WebsiteContent)


@pytest.fixture
def enable_websitecontent_signal():
    """Enable page url update signal"""

    # Disconnect
    pre_save.connect(update_navmenu_on_page_url_change, sender=WebsiteContent)
