""" Github API tests """
import hashlib
from base64 import b64decode, b64encode

import pytest
import yaml
from github import GithubException

from content_sync.apis.github import GithubApiWrapper
from main import features
from users.factories import UserFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name,protected-access


@pytest.fixture
def mock_api_wrapper(settings, mocker):
    """ Create a GithubApiWrapper with a mock Github object"""
    settings.GIT_TOKEN = "faketoken"
    settings.GIT_ORGANIZATION = "fake_org"
    settings.CONTENT_SYNC_RETRIES = 3

    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(5, website=website)

    mocker.patch("content_sync.apis.github.Github", autospec=True)
    return GithubApiWrapper(website)


def test_get_repo(mock_api_wrapper):
    """get_repo should invoke the appropriate PyGithub call"""
    mock_api_wrapper.get_repo()
    mock_api_wrapper.org.get_repo.assert_called_once_with(
        mock_api_wrapper.get_repo_name()
    )


def test_get_repo_create(mocker, mock_api_wrapper):
    """get_repo should create the repo if a 404 is returned"""
    mock_api_wrapper.org.get_repo.side_effect = [
        GithubException(status=404, data={}),
        mocker.Mock(),
    ]
    mock_api_wrapper.get_repo()
    mock_api_wrapper.org.create_repo.assert_called_once_with(
        mock_api_wrapper.get_repo_name(), auto_init=True
    )


@pytest.mark.parametrize("kwargs", [{}, {"private": True}])
def test_create_repo(mock_api_wrapper, kwargs):
    """create_repo should invoke the appropriate PyGithub call"""
    mock_api_wrapper.create_repo(**kwargs)
    mock_api_wrapper.org.create_repo.assert_called_once_with(
        mock_api_wrapper.get_repo_name(), auto_init=True, **kwargs
    )


def test_create_repo_slow_api(mocker, mock_api_wrapper):
    """ Test that the create_repo function will be retried if it fails initially"""
    mock_api_wrapper.org.create_repo.side_effect = [
        GithubException(status=404, data={}),
        GithubException(status=429, data={}),
        mocker.Mock(),
    ]
    new_repo = mock_api_wrapper.create_repo()
    assert mock_api_wrapper.org.create_repo.call_count == 3
    assert new_repo == mock_api_wrapper.get_repo()


def test_create_repo_broken_api(mock_api_wrapper):
    """ Test that the create_repo function fails if the Github API repeatedly fails basic calls"""
    mock_api_wrapper.org.create_repo.side_effect = GithubException(status=404, data={})
    with pytest.raises(Exception):
        mock_api_wrapper.create_repo()


def test_get_branches(mock_api_wrapper, mock_branches):
    """get_branches should return the branches in the website repo"""
    mock_api_wrapper.org.get_repo.return_value.get_branches.return_value = mock_branches
    assert next(mock_api_wrapper.get_branches()) == mock_branches[0]
    assert list(mock_api_wrapper.get_branches()) == mock_branches


@pytest.mark.parametrize("delete_source", [True, False])
def test_create_branch(mocker, mock_api_wrapper, delete_source):
    """create_branch should make relevant github api calls to create a branch and optionally delete a branch"""
    source_branch_name = "main"
    new_branch_name = "preview"
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_api_wrapper.create_branch(
        new_branch_name, source_branch_name, delete_source=delete_source
    )
    mock_repo.get_git_ref.assert_called_once_with(f"heads/{source_branch_name}")
    mock_repo.create_git_ref.assert_called_once_with(
        f"refs/heads/{new_branch_name}", sha=mocker.ANY
    )
    if delete_source:
        mock_repo.get_git_ref.return_value.delete.assert_called_once()
    else:
        mock_repo.get_git_ref.return_value.delete.assert_not_called()


def test_rename_branch(mocker, mock_api_wrapper):
    """rename_branch should call create_branch with delete_source=True"""
    old_branch = "old_branch"
    new_branch = "new_branch"
    mock_api_wrapper.rename_branch(old_branch, new_branch)
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_repo.get_git_ref.assert_called_once_with(f"heads/{old_branch}")
    mock_repo.create_git_ref.assert_called_once_with(
        f"refs/heads/{new_branch}", sha=mocker.ANY
    )
    mock_repo.get_git_ref.return_value.delete.assert_called_once()


def test_upsert_content_file_file_exists(mocker, mock_api_wrapper):
    """upsert_content_file should call repo.update_file"""
    content = mock_api_wrapper.website.websitecontent_set.first()
    message = "upsert file"
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_repo.get_contents.return_value.sha.return_value = hashlib.sha1(b"fake_sha")
    mock_api_wrapper.upsert_content_file(content, message)
    mock_repo.update_file.assert_called_once_with(
        content.content_filepath,
        message,
        mock_api_wrapper.format_content_to_file(content),
        mock_repo.get_contents.return_value.sha,
        committer=mocker.ANY,
        author=mocker.ANY,
        **{},
    )


def test_upsert_content_file_new(mocker, mock_api_wrapper):
    """upsert_content_file should call repo.create_file"""
    content = mock_api_wrapper.website.websitecontent_set.first()
    message = "create file"
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_repo.get_contents.side_effect = GithubException(status=422, data={})
    mock_api_wrapper.upsert_content_file(content, message)
    mock_repo.create_file.assert_called_once_with(
        content.content_filepath,
        message,
        mock_api_wrapper.format_content_to_file(content),
        committer=mocker.ANY,
        author=mocker.ANY,
        **{},
    )


@pytest.mark.parametrize("filepath", [None, ""])
def test_upsert_content_file_no_path(mock_api_wrapper, filepath):
    """upsert_content_file should not call repo.create_file if there is no content_filepath"""
    content = mock_api_wrapper.website.websitecontent_set.first()
    content.content_filepath = filepath
    mock_api_wrapper.upsert_content_file(content, "Create a file")
    mock_api_wrapper.org.get_repo.return_value.create_file.assert_not_called()


def test_upsert_content_files(mocker, mock_api_wrapper):
    """upsert_content_files should process all files in 1 commit per user"""
    for content in mock_api_wrapper.website.websitecontent_set.all()[:2]:
        content.updated_by = UserFactory.create()
        content.save()
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_api_wrapper.upsert_content_files()

    assert (
        mock_repo.create_git_commit.call_count == 3
    )  # 3 users, 2 created above, plus None
    mock_repo.create_git_commit.assert_any_call(
        "Sync all content",
        mock_repo.create_git_tree.return_value,
        [mock_repo.get_git_commit.return_value],
        committer=mocker.ANY,
        author=mocker.ANY,
        **{},
    )

    for content in WebsiteContent.objects.filter(
        id__in=mock_api_wrapper.website.websitecontent_set.values_list("id", flat=True)
    ):
        assert content.content_sync_state.is_synced is True


def test_delete_content_file(mocker, mock_api_wrapper):
    """delete_content_file should call repo.delete_file"""
    content = mock_api_wrapper.website.websitecontent_set.first()
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_repo.get_contents.return_value.sha.return_value = hashlib.sha1(b"fake_sha")
    mock_api_wrapper.delete_content_file(content)
    mock_repo.delete_file.assert_called_once_with(
        content.content_filepath,
        f"Delete {content.content_filepath}",
        mock_repo.get_contents.return_value.sha,
        committer=mocker.ANY,
        **{},
    )


def test_merge_branches(mock_api_wrapper):
    """merge_branches should call repo.merge with correct arguments"""
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_api_wrapper.merge_branches("from_branch", "to_branch")
    mock_repo.merge.assert_called_once_with(
        "to_branch",
        mock_repo.get_branch.return_value.commit.sha,
        "Merge from_branch to to_branch",
    )


@pytest.mark.parametrize("is_anonymous", [True, False])
def test_git_user(settings, mock_api_wrapper, is_anonymous):
    """git_user should return an InputGitAuthor with expected name and email"""
    settings.FEATURES[features.GIT_ANONYMOUS_COMMITS] = is_anonymous
    settings.GIT_DEFAULT_USER_NAME = "GitUser"
    settings.GIT_DEFAULT_USER_EMAIL = "GitUser@git.edu"
    user = UserFactory.create()
    git_author = mock_api_wrapper.git_user(user)
    if is_anonymous:
        assert git_author._identity == {
            "name": f"user_{user.id}",
            "email": settings.GIT_DEFAULT_USER_EMAIL,
        }
    else:
        assert git_author._identity == {"name": user.name, "email": user.email}

    git_author_none = mock_api_wrapper.git_user(None)
    assert git_author_none._identity == {
        "name": settings.GIT_DEFAULT_USER_NAME,
        "email": settings.GIT_DEFAULT_USER_EMAIL,
    }


@pytest.mark.parametrize(
    "markdown, metadata", [[None, None], ["", {"foo": "bar"}], ["markdown", {}]]
)
def test_format_content_to_file(mock_api_wrapper, markdown, metadata):
    """A WebsiteContent object should be transformed into the expected string"""
    content = WebsiteContentFactory.create(markdown=markdown, metadata=metadata)
    assert (
        mock_api_wrapper.format_content_to_file(content)
        == f"---\n{yaml.dump(metadata)}\n---\n{markdown}"
    )


def test_format_file_to_content(mocker, mock_api_wrapper):
    """format_file_to_content should call ocw_import.api.convert_data_to_content with expected args"""
    mock_convert = mocker.patch("content_sync.apis.github.convert_data_to_content")
    mock_content_file = mocker.Mock(
        content=b64encode(b"---\nuid: foo\n----\nTest"), path="src/__index.md"
    )
    mock_api_wrapper.format_file_to_content(mock_content_file)
    mock_convert.assert_called_once_with(
        mock_content_file.path,
        str(b64decode(mock_content_file.content), encoding="utf-8"),
        mock_api_wrapper.website,
        mock_api_wrapper.website.uuid,
    )


def test_custom_github_url(mocker, settings):
    """The github api wrapper should use the GIT_API_URL specified in settings"""
    settings.GIT_API_URL = "http://github.exampled.edu/api/v3"
    settings.GIT_TOKEN = "abcdef"
    mock_github = mocker.patch("content_sync.apis.github.Github", autospec=True)
    GithubApiWrapper(WebsiteFactory.create())
    mock_github.assert_called_once_with(
        base_url=settings.GIT_API_URL, login_or_token=settings.GIT_TOKEN
    )
