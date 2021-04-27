"""Test config for content_sync app"""
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
