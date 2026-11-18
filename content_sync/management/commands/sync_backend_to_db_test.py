"""Tests for the sync_backend_to_db management command."""  # noqa: INP001

from base64 import b64encode
from types import SimpleNamespace

import pytest
from django.core.management import CommandError, call_command

from users.factories import UserFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_backend(mocker):
    """Mock the backend factory."""
    return mocker.patch(
        "content_sync.management.commands.sync_backend_to_db.get_sync_backend"
    )


def test_import_without_commit(mock_backend):
    """Allow an import without an operator or a Git write-back."""
    website = WebsiteFactory.create()

    call_command("sync_backend_to_db", filter=website.name)

    backend = mock_backend.return_value
    backend.sync_all_content_to_db.assert_called_once_with(ref=None, path=None)
    backend.sync_all_content_to_backend.assert_not_called()


@pytest.mark.parametrize("path", ["", "/", "///"])
@pytest.mark.parametrize("commit", [None, "abc123"])
def test_rejects_empty_or_slash_only_path(mock_backend, path, commit):
    """Reject an explicit empty path before selecting a sync backend."""
    website = WebsiteFactory.create()
    user = UserFactory.create()

    with pytest.raises(CommandError, match="--path must name a file or directory"):
        call_command(
            "sync_backend_to_db",
            filter=website.name,
            path=path,
            commit=commit,
            user=user.email,
        )

    mock_backend.assert_not_called()


@pytest.mark.parametrize(
    ("path", "expected_path", "has_content"),
    [
        (None, None, True),
        ("content/page.md", "content/page.md", True),
        ("content/page.md/", "content/page.md", True),
        ("content/bio///", "content/bio", True),
        ("README.md", "README.md", False),
    ],
)
def test_restore_passes_commit_user(
    mock_backend, mocker, path, expected_path, has_content
):
    """Attribute restores and scope path restores to the imported rows."""
    mocker.patch("builtins.input", return_value="Y")
    user = UserFactory.create()
    content = WebsiteContentFactory.create()
    WebsiteContentFactory.create(website=content.website)
    backend = mock_backend.return_value
    imported_ids = [content.pk] if has_content else []
    backend.sync_all_content_to_db.return_value = imported_ids

    call_command(
        "sync_backend_to_db",
        filter=content.website.name,
        commit="abc123",
        path=path,
        user=user.email,
    )

    backend.sync_all_content_to_db.assert_called_once_with(
        ref="abc123", path=expected_path
    )
    backend.sync_all_content_to_backend.assert_called_once()
    sync_options = backend.sync_all_content_to_backend.call_args.kwargs
    assert sync_options["commit_user"] == user
    if path is None:
        assert sync_options["query_set"] is None
    else:
        assert (
            list(sync_options["query_set"].values_list("pk", flat=True)) == imported_ids
        )


def test_github_directory_restore_writes_only_imported_content(mocker, settings):
    """Restore a nested file without committing unrelated dirty content."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    mocker.patch("content_sync.apis.github.get_token", return_value="faketoken")
    github = mocker.patch("content_sync.apis.github.Github", autospec=True)
    repo = github.return_value.get_organization.return_value.get_repo.return_value

    website = WebsiteFactory.create()
    operator = UserFactory.create()
    directory = "content/bio"
    restored = WebsiteContentFactory.create(
        website=website,
        type="bio",
        is_page_content=True,
        dirpath=f"{directory}/nested",
        filename="lesson",
    )
    unrelated = WebsiteContentFactory.create(
        website=website,
        type="bio",
        is_page_content=True,
        dirpath=f"{directory}-archive",
        markdown="Unrelated draft",
    )
    restored_path = f"{restored.dirpath}/{restored.filename}.md"
    historical_markdown = "Historical content"
    historical_file = (
        f"---\nuid: {restored.text_id}\ntitle: Lesson\ncontent_type: bio\n---\n"
        f"{historical_markdown}"
    )
    repo.get_contents.side_effect = [
        [SimpleNamespace(type="dir", path=restored.dirpath)],
        [
            SimpleNamespace(
                type="file",
                path=restored_path,
                content=b64encode(historical_file.encode()),
            )
        ],
    ]

    call_command(
        "sync_backend_to_db",
        filter=website.name,
        commit="abc123",
        path=f"{directory}/",
        user=operator.email,
    )

    repo.create_git_tree.assert_called_once()
    tree_elements = repo.create_git_tree.call_args.args[0]
    assert [element._identity["path"] for element in tree_elements] == [restored_path]  # noqa: SLF001
    restored.refresh_from_db()
    unrelated.refresh_from_db()
    assert restored.markdown == historical_markdown
    assert unrelated.markdown == "Unrelated draft"
    assert not unrelated.content_sync_state.is_synced


@pytest.mark.parametrize("inactive", [True, False])
def test_restore_requires_active_user(mock_backend, inactive):
    """Reject inactive or missing users before restoring content."""
    user_email = UserFactory.create(is_active=False).email if inactive else None

    with pytest.raises(CommandError, match="--user"):
        call_command("sync_backend_to_db", commit="abc123", user=user_email)

    mock_backend.assert_not_called()
