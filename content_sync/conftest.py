"""Test config for content_sync app"""
from base64 import b64encode
from types import SimpleNamespace

import pytest


@pytest.fixture(params=["dev", "not_dev"])
def mock_environments(settings, request):
    """Fixture that tests with dev vs non-dev environment"""
    settings.OCW_STUDIO_ENVIRONMENT = request.param
    settings.ENV_NAME = request.param


@pytest.fixture(params=[True, False])
def mock_concourse_hard_purge(settings, request):
    """Fixture that tests with True and False for settings.CONCOURSE_HARD_PURGE"""
    settings.CONCOURSE_HARD_PURGE = request.param


@pytest.fixture
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


@pytest.fixture
def github_content_file(mocker):
    """Fixture that returns a mocked Github ContentFile object with some related properties"""
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
    settings.CONCOURSE_PASSWORD = "pass"  # pragma: allowlist secret
    settings.CONCOURSE_TEAM = "ocwtest"
    settings.AWS_PREVIEW_BUCKET_NAME = "preview_bucket"
    settings.AWS_PUBLISH_BUCKET_NAME = "publish_bucket"
    settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME = "offline_preview_bucket"
    settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME = "offline_publish_bucket"
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"
    settings.GIT_BRANCH_PREVIEW = "preview"
    settings.GIT_BRANCH_RELEASE = "release"
    settings.GIT_DOMAIN = "test.github.edu"
    settings.GIT_ORGANIZATION = "test_org"
    settings.GITHUB_WEBHOOK_BRANCH = "release"
    settings.SITE_BASE_URL = "http://test.edu"
    settings.API_BEARER_TOKEN = "abc123"  # pragma: allowlist secret
    settings.SEARCH_API_URL = "http://test.edu/api/v0/search"
    settings.OCW_GTM_ACCOUNT_ID = "abc123"
