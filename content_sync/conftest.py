"""Test config for content_sync app"""
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from websites.constants import STARTER_SOURCE_GITHUB
from websites.factories import WebsiteFactory, WebsiteStarterFactory
from websites.models import Website, WebsiteStarter


@pytest.hookimpl(tryfirst=True)
def pytest_keyboard_interrupt(excinfo):  # noqa: ARG001
    """If tests are aborted locally with SIGINT, clean up models"""
    Website.objects.all().delete()
    WebsiteStarter.objects.all().delete()


@pytest.fixture(params=["dev", "not_dev"])
def mock_environments(settings, request):  # noqa: PT004
    """Fixture that tests with dev vs non-dev environment"""
    settings.OCW_STUDIO_ENVIRONMENT = request.param
    settings.ENV_NAME = request.param
    settings.ENVIRONMENT = request.param


@pytest.fixture(params=[True, False])
def mock_concourse_hard_purge(settings, request):  # noqa: PT004
    """Fixture that tests with True and False for settings.CONCOURSE_HARD_PURGE"""
    settings.CONCOURSE_HARD_PURGE = request.param


@pytest.fixture()
def mock_branches(settings, mocker):
    """Return mock github branches with names"""
    mocked_branches = []
    for branch_name in [
        settings.GIT_BRANCH_MAIN,
        settings.GIT_BRANCH_PREVIEW,
        settings.GIT_BRANCH_RELEASE,
    ]:
        mock_branch = mocker.Mock()
        mock_branch.name = branch_name
        mocked_branches.append(mock_branch)
    return mocked_branches


@pytest.fixture()
def github_content_file(mocker):
    """Fixture that returns a mocked Github ContentFile object with some related properties"""  # noqa: E501
    content_str = "my file content"
    path = "/path/to/file.md"
    return SimpleNamespace(
        obj=mocker.Mock(
            type="file", path=path, content=b64encode(content_str.encode("utf-8"))
        ),
        path=path,
        content_str=content_str,
    )


@pytest.fixture(autouse=True)
def required_concourse_settings(settings):
    """Other required settings for concourse pipelines"""
    settings.CONCOURSE_URL = "http://localconcourse.edu"
    settings.CONCOURSE_USERNAME = "test"
    settings.CONCOURSE_PASSWORD = "pass"  # pragma: allowlist secret  # noqa: S105
    settings.CONCOURSE_TEAM = "ocwtest"
    settings.AWS_ARTIFACTS_BUCKET_NAME = "artifacts_bucket"
    settings.AWS_PREVIEW_BUCKET_NAME = "preview_bucket"
    settings.AWS_PUBLISH_BUCKET_NAME = "publish_bucket"
    settings.AWS_TEST_BUCKET_NAME = "test_bucket"
    settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME = "offline_preview_bucket"
    settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME = "offline_publish_bucket"
    settings.AWS_OFFLINE_TEST_BUCKET_NAME = "offline_test_bucket"
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"
    settings.GIT_BRANCH_PREVIEW = "preview"
    settings.GIT_BRANCH_RELEASE = "release"
    settings.GIT_DOMAIN = "test.github.edu"
    settings.GIT_ORGANIZATION = "test_org"
    settings.GITHUB_WEBHOOK_BRANCH = "release"
    settings.SITE_BASE_URL = "http://test.edu"
    settings.API_BEARER_TOKEN = "abc123"  # pragma: allowlist secret  # noqa: S105
    settings.SEARCH_API_URL = "http://test.edu/api/v0/search"
    settings.OCW_GTM_ACCOUNT_ID = "abc123"
    settings.OCW_WWW_TEST_SLUG = "ocw-ci-test-www"
    settings.OCW_COURSE_TEST_SLUG = "ocw-ci-test-course"
    return settings


@pytest.fixture(scope="module")
def mass_build_websites(django_db_setup, django_db_blocker):  # noqa: ARG001
    """Generate websites for testing the mass build pipeline"""
    with django_db_blocker.unblock():
        now = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        total_sites = 6
        ocw_hugo_projects_path = "https://github.com/org/repo"
        root_starter = WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB,
            path=ocw_hugo_projects_path,
            slug="root-website-starter",
        )
        starter = WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path=ocw_hugo_projects_path
        )
        root_website = WebsiteFactory.create(name="root-website", starter=root_starter)
        batch_sites = WebsiteFactory.create_batch(
            total_sites, starter=starter, draft_publish_date=now, publish_date=now
        )
        batch_sites.append(root_website)
        yield batch_sites
        for site in batch_sites:
            site.delete()
        starter.delete()
        root_starter.delete()
