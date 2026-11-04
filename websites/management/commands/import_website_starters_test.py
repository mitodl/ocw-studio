"""Tests for the import_website_starters command"""  # noqa: INP001

from types import SimpleNamespace

import pytest
from django.core.management import CommandError, call_command

GIT_URL = "https://github.com/testorg/ocw-hugo-projects"
MODULE = "websites.management.commands.import_website_starters"


@pytest.fixture
def mock_repo(mocker):
    """Mock the GitHub repo the command reads"""
    mock_github = mocker.patch(f"{MODULE}.Github")
    return mock_github.return_value.get_organization.return_value.get_repo.return_value


@pytest.fixture
def mock_sync(mocker):
    """Mock the starter sync"""
    return mocker.patch(f"{MODULE}.sync_starter_configs")


def test_import_website_starters_reads_the_branch(
    mocker, settings, mock_repo, mock_sync
):
    """Without tag releases the command imports from the branch, as before"""
    settings.OCW_HUGO_TAG_RELEASES = False
    mocker.patch(
        f"{MODULE}.find_files_recursive", return_value=["site/ocw-studio.yaml"]
    )
    call_command("import_website_starters", GIT_URL, commit="abc123")
    mock_sync.assert_called_once_with(
        repo_url=GIT_URL,
        config_files=["site/ocw-studio.yaml"],
        commit="abc123",
        tag=None,
    )


@pytest.fixture
def tag_releases(mocker, settings):
    """Turn on tag releases for the release-candidate pointer"""
    settings.OCW_HUGO_TAG_RELEASES = True
    settings.GITHUB_WEBHOOK_BRANCH = "release-candidate"
    mocker.patch("content_sync.utils.is_dev", return_value=False)


@pytest.mark.parametrize(
    ("tag_option", "expected_tag"),
    [({}, "2026.11.10.1"), ({"tag": "2026.11.9.2"}, "2026.11.9.2")],
)
def test_import_website_starters_reads_a_release_tag(  # noqa: PLR0913, PLR0917
    mocker, tag_releases, mock_repo, mock_sync, tag_option, expected_tag
):
    """With tag releases on the command reads the newest release tag, or the one named"""
    mock_repo.get_tags.return_value = [
        SimpleNamespace(name=name) for name in ("2026.11.9.2", "2026.11.10.1", "v1.0.0")
    ]
    mock_repo.get_commit.return_value.sha = "tagcommit"
    mock_find = mocker.patch(
        f"{MODULE}.find_files_recursive", return_value=["site/ocw-studio.yaml"]
    )
    call_command("import_website_starters", GIT_URL, **tag_option)
    mock_repo.get_commit.assert_called_once_with(expected_tag)
    assert mock_find.call_args.kwargs["commit"] == "tagcommit"
    mock_sync.assert_called_once_with(
        repo_url=GIT_URL,
        config_files=["site/ocw-studio.yaml"],
        commit="tagcommit",
        tag=expected_tag,
    )


def test_import_website_starters_without_a_release_tag(
    tag_releases, mock_repo, mock_sync
):
    """With tag releases on and no matching tag the command says so and imports nothing"""
    mock_repo.get_tags.return_value = []
    with pytest.raises(CommandError):
        call_command("import_website_starters", GIT_URL)
    mock_sync.assert_not_called()
