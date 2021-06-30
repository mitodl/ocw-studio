""" Github API tests """
import hashlib
from types import SimpleNamespace

import factory
import pytest
from django.conf import settings
from github import GithubException

from content_sync.apis.github import (
    GIT_DATA_FILEPATH,
    GithubApiWrapper,
    get_destination_filepath,
    sync_starter_configs,
)
from content_sync.backends.base import SITE_CONFIG_FILENAME
from main import features
from users.factories import UserFactory
from websites.constants import STARTER_SOURCE_GITHUB
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import WebsiteContent, WebsiteStarter
from websites.site_config_api import ConfigItem, SiteConfig
from websites.utils import format_site_config_env


pytestmark = pytest.mark.django_db

# pylint:disable=redefined-outer-name,protected-access,too-many-arguments,unused-argument


@pytest.fixture
def db_data():
    """Fixture that seeds the database with data needed for this test suite"""
    users = UserFactory.create_batch(2)
    website = WebsiteFactory.create()
    website_contents = WebsiteContentFactory.create_batch(
        5,
        website=website,
        updated_by=factory.Iterator([users[0], users[0], users[0], users[1], users[1]]),
    )
    return SimpleNamespace(
        users=users, website=website, website_contents=website_contents
    )


@pytest.fixture
def mock_api_wrapper(settings, mocker, db_data):
    """Create a GithubApiWrapper with a mock Github object"""
    settings.GIT_TOKEN = "faketoken"
    settings.GIT_ORGANIZATION = "fake_org"
    settings.CONTENT_SYNC_RETRIES = 3

    mocker.patch("content_sync.apis.github.Github", autospec=True)
    return GithubApiWrapper(
        website=db_data.website, site_config=SiteConfig(db_data.website.starter.config)
    )


@pytest.fixture
def mock_github(mocker):
    """ Return a mock Github class"""
    return mocker.patch("content_sync.apis.github.Github")


@pytest.fixture
def patched_file_serialize(mocker):
    """Patches function that serializes website content to file contents"""
    return mocker.patch(
        "content_sync.apis.github.serialize_content_to_file",
    )


def fake_destination_filepath(website_content: WebsiteContent, *args) -> str:
    """Returns a fake destination filepath for some WebsiteContent record"""
    return f"path/to/{website_content.filename}.md"


@pytest.fixture
def patched_destination_filepath(mocker):
    """Patches the get_destination_filepath API function"""
    return mocker.patch(
        "content_sync.apis.github.get_destination_filepath", fake_destination_filepath
    )


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
        mock_api_wrapper.get_repo_name(), auto_init=False
    )


@pytest.mark.parametrize("kwargs", [{}, {"private": True}])
def test_create_repo(mock_api_wrapper, kwargs):
    """create_repo should invoke the appropriate PyGithub call"""
    mock_api_wrapper.create_repo(**kwargs)
    mock_api_wrapper.org.create_repo.assert_called_once_with(
        mock_api_wrapper.get_repo_name(), auto_init=False, **kwargs
    )


def test_create_repo_slow_api(mocker, mock_api_wrapper, mock_branches):
    """ Test that the create_repo function will be retried if it fails initially"""
    mock_api_wrapper.org.create_repo.side_effect = [
        GithubException(status=404, data={}),
        GithubException(status=429, data={}),
        mocker.Mock(get_branches=mocker.Mock(return_value=mock_branches[0:1])),
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


@pytest.mark.parametrize("is_existing_file", [True, False])
def test_upsert_content_file(
    mocker,
    db_data,
    mock_api_wrapper,
    patched_file_serialize,
    patched_destination_filepath,
    is_existing_file,
):
    """upsert_content_file should call the correct Github API method depending on whether or not the file exists"""
    content = db_data.website_contents[0]
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    if is_existing_file:
        mock_repo.get_contents.return_value.sha.return_value = hashlib.sha1(b"fake_sha")
        github_api_method = mock_repo.update_file
    else:
        mock_repo.get_contents.side_effect = GithubException(status=422, data={})
        github_api_method = mock_repo.create_file
    serialized_contents = "my contents"
    patched_file_serialize.return_value = serialized_contents
    mock_api_wrapper.upsert_content_file(content)

    patched_file_serialize.assert_called_once_with(
        site_config=mock_api_wrapper.site_config, website_content=content
    )
    github_api_method.assert_called_once()
    expected_filepath = fake_destination_filepath(content)
    if is_existing_file:
        github_api_method.assert_called_once_with(
            expected_filepath,
            f"Update {expected_filepath}",
            serialized_contents,
            mock_repo.get_contents.return_value.sha,
            committer=mocker.ANY,
            author=mocker.ANY,
            **{},
        )
    else:
        github_api_method.assert_called_once_with(
            expected_filepath,
            f"Create {expected_filepath}",
            serialized_contents,
            committer=mocker.ANY,
            author=mocker.ANY,
            **{},
        )


@pytest.mark.parametrize("filepath", [None, ""])
def test_upsert_content_file_no_path(mocker, mock_api_wrapper, db_data, filepath):
    """upsert_content_file should not call repo.create_file if there is no destination filepath"""
    mocker.patch(
        "content_sync.apis.github.get_destination_filepath", return_value=filepath
    )
    content = db_data.website_contents[0]
    mock_api_wrapper.upsert_content_file(content)
    mock_api_wrapper.org.get_repo.return_value.create_file.assert_not_called()


def test_upsert_content_files(mocker, mock_api_wrapper, db_data):
    """upsert_content_files should upsert all content files for each distinct user in one commit per user"""
    expected_num_users = 2
    # Create a record and delete it to test that upsert_content_files_for_user still queries for deleted records
    content_to_delete = WebsiteContentFactory.create(website=db_data.website)
    content_to_delete.delete()
    patched_upsert_for_user = mocker.patch.object(
        mock_api_wrapper, "upsert_content_files_for_user"
    )
    mock_api_wrapper.upsert_content_files()
    assert patched_upsert_for_user.call_count == (expected_num_users + 1)
    for user in db_data.users:
        patched_upsert_for_user.assert_any_call(user.id)
    patched_upsert_for_user.assert_any_call(None)


def test_upsert_content_files_for_user(
    mocker,
    mock_api_wrapper,
    db_data,
    patched_file_serialize,
    patched_destination_filepath,
):
    """
    upsert_content_files_for_user should upsert all content files for a user in 1 commit and modify ContentSyncState
    records to reflect the results.
    """
    mock_git_tree_element = mocker.patch("content_sync.apis.github.InputGitTreeElement")
    for content in db_data.website_contents:
        content.content_sync_state.data = {
            GIT_DATA_FILEPATH: fake_destination_filepath(content)
        }
        content.content_sync_state.save()
    db_data.website_contents[2].delete()  # ensure we record a delete for the user
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    user = db_data.users[0]
    expected_contents_count = 3
    expected_contents = db_data.website_contents[0:expected_contents_count]
    serialized_contents = "my contents"
    patched_file_serialize.return_value = serialized_contents
    mock_api_wrapper.upsert_content_files_for_user(user.id)

    assert mock_git_tree_element.call_count == len(expected_contents)
    for content in expected_contents:
        if content.deleted:
            mock_git_tree_element.assert_any_call(
                fake_destination_filepath(content), "100644", "blob", sha=None
            )
        else:
            mock_git_tree_element.assert_any_call(
                fake_destination_filepath(content), "100644", "blob", mocker.ANY
            )

    mock_repo.create_git_commit.assert_called_once_with(
        "Sync all content",
        mock_repo.create_git_tree.return_value,
        [mock_repo.get_git_commit.return_value],
        committer=mocker.ANY,
        author=mocker.ANY,
    )

    for content in expected_contents:
        if not content.deleted:
            content.refresh_from_db()
            assert content.content_sync_state.is_synced is True
            assert (
                content.content_sync_state.current_checksum
                == content.calculate_checksum()
            )


@pytest.mark.parametrize(
    "field, value",
    [
        ["markdown", "NEW"],
        ["metadata", '{"foo": 2}'],
        ["dirpath", "brand/new/dirpath"],
        ["filename", "brand-new-test-case-filename"],
    ],
)
def test_upsert_content_files_modified_only(
    mocker,
    mock_api_wrapper,
    db_data,
    patched_file_serialize,
    patched_destination_filepath,
    field,
    value,
):
    """upsert_content_files_for_user should process only the file with a modified field"""
    mock_git_tree_element = mocker.patch("content_sync.apis.github.InputGitTreeElement")
    user = db_data.users[0]
    expected_contents_count = 3
    website_contents = [
        content for content in db_data.website_contents if content.updated_by == user
    ]
    assert len(website_contents) == expected_contents_count

    # Make all content appear to be synced
    for content in website_contents:
        content_sync = content.content_sync_state
        content_sync.synced_checksum = content_sync.content.calculate_checksum()
        content_sync.save()

    # Update the field for one WebsiteContent object
    content = website_contents[0]
    setattr(content, field, value)
    content.save()

    mock_api_wrapper.upsert_content_files_for_user(user.id)
    mock_git_tree_element.called_once_with(
        fake_destination_filepath(content), "100644", "blob", mocker.ANY
    )

    content.refresh_from_db()
    assert content.content_sync_state.is_synced is True


def test_upsert_content_files_modified_filepath(
    mocker,
    mock_api_wrapper,
    db_data,
    patched_file_serialize,
    patched_destination_filepath,
):
    """upsert_content_files_for_user should save git filepath in sync state and remove old paths from git"""
    mock_git_tree_element = mocker.patch("content_sync.apis.github.InputGitTreeElement")
    user = db_data.users[0]
    content = db_data.website_contents[0]
    old_filepath = fake_destination_filepath(content)
    sync_state = content.content_sync_state
    mock_api_wrapper.upsert_content_files_for_user(user.id)

    sync_state.refresh_from_db()
    assert sync_state.data[GIT_DATA_FILEPATH] == old_filepath
    content.filename = "new-test-case-filename.xyz"
    # NOTE: This test case relies on the fact that this change triggers the creation of a new ContentSyncState
    content.save()
    new_filepath = fake_destination_filepath(content)
    mock_api_wrapper.upsert_content_files_for_user(user.id)

    mock_git_tree_element.assert_any_call(new_filepath, "100644", "blob", mocker.ANY)
    mock_git_tree_element.assert_any_call(old_filepath, "100644", "blob", sha=None)
    sync_state.refresh_from_db()
    assert sync_state.data[GIT_DATA_FILEPATH] == new_filepath


def test_upsert_content_files_deleted(
    mocker,
    mock_api_wrapper,
    db_data,
    patched_file_serialize,
    patched_destination_filepath,
):
    """upsert_content_files should process deleted files"""
    mock_git_tree_element = mocker.patch("content_sync.apis.github.InputGitTreeElement")

    # Make all content appear to be synced
    for content in db_data.website_contents:
        content_sync = content.content_sync_state
        content_sync.synced_checksum = content_sync.content.calculate_checksum()
        content_sync.data = {
            "filepath": fake_destination_filepath(content_sync.content)
        }
        content_sync.save()

    # Mark the content as soft-deleted
    content = db_data.website_contents[0]
    content.delete()

    mock_api_wrapper.upsert_content_files()
    mock_git_tree_element.called_once_with(
        fake_destination_filepath(content), "100644", "blob", sha=None
    )

    assert WebsiteContent.all_objects.filter(id=content.id).exists() is False


def test_delete_content_file(mocker, mock_api_wrapper, patched_destination_filepath):
    """delete_content_file should call repo.delete_file"""
    content = mock_api_wrapper.website.websitecontent_set.first()
    mock_repo = mock_api_wrapper.org.get_repo.return_value
    mock_repo.get_contents.return_value.sha.return_value = hashlib.sha1(b"fake_sha")
    mock_api_wrapper.delete_content_file(content)
    expected_filepath = fake_destination_filepath(content)
    mock_repo.delete_file.assert_called_once_with(
        expected_filepath,
        f"Delete {expected_filepath}",
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


def test_custom_github_url(mocker, settings):
    """The github api wrapper should use the GIT_API_URL specified in settings"""
    settings.GIT_API_URL = "http://github.example.edu/api/v3"
    settings.GIT_TOKEN = "abcdef"
    mock_github = mocker.patch("content_sync.apis.github.Github", autospec=True)
    GithubApiWrapper(website=mocker.Mock(), site_config=mocker.Mock())
    mock_github.assert_called_once_with(
        login_or_token=settings.GIT_TOKEN, base_url=settings.GIT_API_URL
    )


def test_custom_default_url(mocker, settings):
    """The github api wrapper should use the default Github url and not pass a base_url kwarg"""
    settings.GIT_API_URL = None
    settings.GIT_TOKEN = "abcdef"
    mock_github = mocker.patch("content_sync.apis.github.Github", autospec=True)
    GithubApiWrapper(website=mocker.Mock(), site_config=mocker.Mock())
    mock_github.assert_called_once_with(login_or_token=settings.GIT_TOKEN)


def test_create_repo_new(mocker, mock_api_wrapper, mock_branches):
    """ Test that the create_repo function completes without errors and calls expected api functions"""
    mock_api_wrapper.org.create_repo.return_value = mocker.Mock(
        default_branch=settings.GIT_BRANCH_MAIN,
        get_branches=mocker.Mock(return_value=mock_branches[0:1]),
    )
    new_repo = mock_api_wrapper.create_repo()
    mock_api_wrapper.org.create_repo.assert_called_once_with(
        mock_api_wrapper.get_repo_name(), auto_init=False
    )
    for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
        new_repo.create_git_ref.assert_any_call(f"refs/heads/{branch}", sha=mocker.ANY)
    with pytest.raises(AssertionError):
        new_repo.create_git_ref.assert_any_call(
            f"refs/heads/{settings.GIT_BRANCH_MAIN}", sha=mocker.ANY
        )
    assert new_repo == mock_api_wrapper.get_repo()


def test_create_repo_again(mocker, mock_api_wrapper):
    """ Test that the create_repo function will try retrieving a repo if api.create_repo fails"""
    mock_log = mocker.patch("content_sync.apis.github.log.debug")
    mock_api_wrapper.org.create_repo.side_effect = GithubException(status=422, data={})
    new_repo = mock_api_wrapper.create_repo()
    assert new_repo is not None
    assert mock_api_wrapper.org.get_repo.call_count == 1
    mock_log.assert_called_once_with(
        "Repo already exists: %s", mock_api_wrapper.website.name
    )


def test_create_backend_custom_default_branch(
    settings, mocker, mock_api_wrapper, mock_branches
):
    """ Test that the create_backend function creates a custom default branch name """
    settings.GIT_BRANCH_MAIN = "testing"
    mock_api_wrapper.org.create_repo.return_value = mocker.Mock(
        default_branch="main", get_branches=mocker.Mock(return_value=mock_branches[0:1])
    )
    new_repo = mock_api_wrapper.create_repo()
    for branch in ["testing", settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
        new_repo.create_git_ref.assert_any_call(f"refs/heads/{branch}", sha=mocker.ANY)


def test_create_backend_two_branches_already_exist(
    mocker, mock_api_wrapper, mock_branches
):
    """ Test that the create_backend function only creates branches that don't exist """
    mock_api_wrapper.org.create_repo.return_value = mocker.Mock(
        default_branch=settings.GIT_BRANCH_MAIN,
        get_branches=mocker.Mock(return_value=mock_branches[0:2]),
    )
    new_repo = mock_api_wrapper.create_repo()
    with pytest.raises(AssertionError):
        new_repo.create_git_ref.assert_any_call(
            f"refs/heads/{settings.GIT_BRANCH_PREVIEW}", sha=mocker.ANY
        )
    new_repo.create_git_ref.assert_any_call(
        f"refs/heads/{settings.GIT_BRANCH_RELEASE}", sha=mocker.ANY
    )
    assert new_repo == mock_api_wrapper.get_repo()


@pytest.mark.parametrize(
    "has_missing_name, is_bad_config_item",
    [
        [True, False],
        [False, True],
    ],
)
def test_get_destination_filepath_errors(mocker, has_missing_name, is_bad_config_item):
    """
    get_destination_filepath should log an error and return None if the site config is missing the given name, or if
    the config item does not have a properly configured destination.
    """
    patched_log = mocker.patch("content_sync.apis.github.log")
    # From basic-site-config.yml
    config_item_name = "blog"
    if is_bad_config_item:
        mocker.patch.object(
            SiteConfig,
            "find_item_by_name",
            return_value=ConfigItem(
                item={"name": config_item_name, "poorly": "configured"}
            ),
        )
    starter = WebsiteStarterFactory.build()
    content = WebsiteContentFactory.build(
        is_page_content=False,
        type="non-existent-config-name" if has_missing_name else config_item_name,
    )
    return_value = get_destination_filepath(
        content=content, site_config=SiteConfig(starter.config)
    )
    patched_log.error.assert_called_once()
    assert return_value is None


def test_sync_starter_configs_success_create(mocker, mock_github):
    """sync_starter_configs should successfully create new WebsiteStarter objects"""
    config_filenames = [
        "site-1/ocw-studio.yaml",
        "site-2/ocw-studio.yaml",
        "ocw-studio.yaml",
    ]
    git_url = "https://github.com/testorg/ocws-configs"
    config_content = b"---\ncollections: []"
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.side_effect = [
        mocker.Mock(path=config_filenames[0], decoded_content=config_content),
        mocker.Mock(path=config_filenames[1], decoded_content=config_content),
        mocker.Mock(path=config_filenames[2], decoded_content=config_content),
    ]
    sync_starter_configs(git_url, config_filenames)
    for filename in config_filenames:
        expected_slug = filename.split("/")[0] if "/" in filename else "ocws-configs"
        assert WebsiteStarter.objects.filter(
            source=STARTER_SOURCE_GITHUB,
            path="/".join([git_url, expected_slug]),
            slug=expected_slug,
            name=expected_slug,
            config={"collections": []},
        ).exists()


def test_sync_starter_configs_success_update(mocker, mock_github):
    """sync_starter_configs should successfully update a WebsiteStarter object"""
    git_url = "https://github.com/testorg/ocws-configs"
    slug = "site-1"
    config_content = b"---\ncollections: []"
    file_list = [f"{slug}/ocw-studio.yaml"]

    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB,
        path=f"{git_url}/{slug}",
        slug=slug,
        name="Site 1",
        config={"foo": "bar"},
    )
    starter_count = WebsiteStarter.objects.count()

    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.return_value = mocker.Mock(
        path=file_list[0], decoded_content=config_content
    )

    sync_starter_configs(git_url, file_list)
    assert WebsiteStarter.objects.count() == starter_count
    starter.refresh_from_db()
    assert starter.name == "Site 1"
    assert starter.config == {"collections": []}


def test_sync_starter_configs_success_partial_failure(mocker, mock_github):
    """sync_starter_configs should detect & gracefully handle an invalid config"""
    config_filenames = ["site-1/ocw-studio.yaml", "site-2/ocw-studio.yaml"]
    git_url = "https://github.com/testorg/ocws-configs"
    mock_log = mocker.patch("content_sync.apis.github.log.exception")
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.side_effect = [
        mocker.Mock(path=config_filenames[0], decoded_content=b"---\ncollections: []"),
        mocker.Mock(
            path=config_filenames[1], decoded_content=b"---\nfcollections: []\nfoo: bar"
        ),
    ]
    sync_starter_configs(git_url, config_filenames)
    mock_log.assert_called_once_with(
        "Invalid site config YAML found in %s", config_filenames[1]
    )
    assert WebsiteStarter.objects.filter(
        source=STARTER_SOURCE_GITHUB,
        path=f"{git_url}/site-1",
        slug="site-1",
        name="site-1",
        config={"collections": []},
    ).exists()
    assert not WebsiteStarter.objects.filter(
        path=f"{git_url}/site-2",
    ).exists()


def test_sync_starter_configs_exception(mocker, mock_github):
    """sync_starter_configs should detect & gracefully handle any exception"""
    config_filenames = ["site-1/ocw-studio.yaml", "site-2/ocw-studio.yaml"]
    git_url = "https://github.com/testorg/ocws-configs"
    mock_log = mocker.patch("content_sync.apis.github.log.exception")
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.side_effect = [
        KeyError("invalid key")
    ]
    sync_starter_configs(git_url, config_filenames)
    for filename in config_filenames:
        mock_log.assert_any_call("Error processing config file %s", filename)


def test_sync_starter_configs_webhook_branch_hash_mismatch(mocker, mock_github):
    """A push to a branch other than the default branch without GITHUB_WEBHOOK_BRANCH should not trigger a starter update"""
    git_url = "https://github.com/testorg/ocws-configs"
    config_filenames = ["site-1/ocw-studio.yaml", "site-2/ocw-studio.yaml"]
    mock_github.return_value.get_organization.return_value.get_repo.return_value.default_branch.return_value = (
        settings.GIT_BRANCH_MAIN
    )
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_branch.return_value = mocker.Mock(
        commit=mocker.Mock(sha="abc123")
    )
    fake_commit = "def456"
    sync_starter_configs(git_url, config_filenames, fake_commit)
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.assert_not_called()


def test_sync_starter_configs_webhook_branch_hash_match(mocker, mock_github):
    """
    A push to the branch set in settings.GITHUB_WEBHOOK_BRANCH should trigger
    getting that branch and then the config files themselves
    """
    git_url = "https://github.com/testorg/ocws-configs"
    config_filenames = ["site-1/ocw-studio.yaml", "site-2/ocw-studio.yaml"]
    fake_commit = "abc123"
    release_branch = "release"
    config_content = b"---\ncollections: []"
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.side_effect = [
        mocker.Mock(path=config_filenames[0], decoded_content=config_content),
        mocker.Mock(path=config_filenames[1], decoded_content=config_content),
    ]
    settings.GITHUB_WEBHOOK_BRANCH = release_branch
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_branch.return_value = mocker.Mock(
        commit=mocker.Mock(sha=fake_commit)
    )
    sync_starter_configs(git_url, config_filenames, fake_commit)
    mock_github.return_value.get_organization.return_value.get_repo.return_value.get_branch.assert_called_once_with(
        release_branch
    )
    for config_file in config_filenames:
        mock_github.return_value.get_organization.return_value.get_repo.return_value.get_contents.assert_any_call(
            config_file, fake_commit
        )


@pytest.mark.parametrize("file_exists", [True, False])
def test_upsert_site_config_file(mocker, settings, mock_api_wrapper, file_exists):
    """upsert_site_config_file should make a git api call to create or update a new file"""
    settings.CONTENT_SYNC_RETRIES = 0
    mock_api_wrapper.repo = mocker.Mock()
    if file_exists:
        mock_api_wrapper.repo.get_contents.return_value.sha.return_value = hashlib.sha1(
            b"fake_sha"
        )
        mock_api_wrapper.upsert_site_config_file(commit_msg="Second commit")
        mock_api_wrapper.repo.update_file.assert_called_once_with(
            SITE_CONFIG_FILENAME,
            "Second commit",
            format_site_config_env(mock_api_wrapper.website),
            mock_api_wrapper.repo.get_contents.return_value.sha,
            committer=mocker.ANY,
            author=mocker.ANY,
        )
    else:
        mock_api_wrapper.repo.get_contents.side_effect = GithubException(
            status=400, data={}
        )
        mock_api_wrapper.upsert_site_config_file()
        mock_api_wrapper.repo.create_file.assert_called_once_with(
            SITE_CONFIG_FILENAME,
            "Initial commit",
            format_site_config_env(mock_api_wrapper.website),
            committer=mocker.ANY,
            author=mocker.ANY,
        )
