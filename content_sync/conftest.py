"""Test config for content_sync app"""
import os
from base64 import b64encode
from types import SimpleNamespace

import pytest


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
    """ Other required settings for concourse pipelines """
    settings.CONCOURSE_URL = "http://localconcourse.edu"
    settings.CONCOURSE_USERNAME = "test"
    settings.CONCOURSE_PASSWORD = "pass"
    settings.CONCOURSE_TEAM = "ocwtest"
    settings.AWS_PREVIEW_BUCKET_NAME = "preview_bucket"
    settings.AWS_PUBLISH_BUCKET_NAME = "publish_bucket"
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket"
    settings.GIT_BRANCH_PREVIEW = "preview"
    settings.GIT_BRANCH_RELEASE = "release"
    settings.GIT_DOMAIN = "test.github.edu"
    settings.GIT_ORGANIZATION = "test_org"
    settings.GITHUB_WEBHOOK_BRANCH = "release"
    os.environ["OCW_STUDIO_BASE_URL"] = "http://test.edu"
