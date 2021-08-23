"""Project conftest"""
import os
from types import SimpleNamespace

import pytest
import yaml

from fixtures.common import *  # pylint:disable=wildcard-import,unused-wildcard-import
from websites.constants import OMNIBUS_STARTER_SLUG
from websites.models import WebsiteStarter
from websites.site_config_api import SiteConfig


@pytest.fixture(autouse=True)
def default_settings(settings):
    """Set default settings for all tests"""
    settings.DISABLE_WEBPACK_LOADER_STATS = True


@pytest.fixture()
def mocked_celery(mocker):
    """Mock object that patches certain celery functions"""
    exception_class = TabError
    replace_mock = mocker.patch(
        "celery.app.task.Task.replace", autospec=True, side_effect=exception_class
    )
    group_mock = mocker.patch("celery.group", autospec=True)
    chain_mock = mocker.patch("celery.chain", autospec=True)

    yield SimpleNamespace(
        replace=replace_mock,
        group=group_mock,
        chain=chain_mock,
        replace_exception_class=exception_class,
    )


@pytest.fixture()
@pytest.mark.django_db
def course_starter(settings):
    """Returns the 'course'-type WebsiteStarter that is seeded in a data migration"""
    return WebsiteStarter.objects.get(slug=settings.OCW_IMPORT_STARTER_SLUG)


@pytest.fixture()
@pytest.mark.django_db
def omnibus_starter():
    """Returns the omnibus WebsiteStarter that is seeded in a data migration"""
    return WebsiteStarter.objects.get(slug=OMNIBUS_STARTER_SLUG)


@pytest.fixture()
@pytest.mark.django_db
def omnibus_config(settings):
    """Returns the omnibus site config"""
    with open(
        os.path.join(settings.BASE_DIR, "localdev/configs/omnibus-site-config.yml")
    ) as f:
        raw_config = f.read().strip()
    parsed_config = yaml.load(raw_config, Loader=yaml.SafeLoader)
    return SiteConfig(parsed_config)


def pytest_addoption(parser):
    """Pytest hook that adds command line parameters"""
    parser.addoption(
        "--simple",
        action="store_true",
        help="Run tests only (no cov, warning output silenced)",
    )


def pytest_configure(config):
    """Pytest hook to perform some initial configuration"""
    if getattr(config.option, "simple") is True:
        # NOTE: These plugins are already configured by the time the pytest_cmdline_main hook is run, so we can't
        #       simply add/alter the command line options in that hook. This hook is being used to
        #       reconfigure/unregister plugins that we can't change via the pytest_cmdline_main hook.
        # Switch off coverage plugin
        cov = config.pluginmanager.get_plugin("_cov")
        cov.options.no_cov = True
        # Remove warnings plugin to suppress warnings
        if config.pluginmanager.has_plugin("warnings"):
            warnings_plugin = config.pluginmanager.get_plugin("warnings")
            config.pluginmanager.unregister(warnings_plugin)
