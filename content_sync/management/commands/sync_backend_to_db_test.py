"""Tests for the sync_backend_to_db management command."""  # noqa: INP001

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


@pytest.mark.parametrize(
    ("path", "has_content"),
    [(None, True), ("content/page.md", True), ("README.md", False)],
)
def test_restore_passes_commit_user(mock_backend, mocker, path, has_content):
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

    backend.sync_all_content_to_db.assert_called_once_with(ref="abc123", path=path)
    backend.sync_all_content_to_backend.assert_called_once()
    sync_options = backend.sync_all_content_to_backend.call_args.kwargs
    assert sync_options["commit_user"] == user
    if path is None:
        assert sync_options["query_set"] is None
    else:
        assert (
            list(sync_options["query_set"].values_list("pk", flat=True)) == imported_ids
        )


@pytest.mark.parametrize("inactive", [True, False])
def test_restore_requires_active_user(mock_backend, inactive):
    """Reject inactive or missing users before restoring content."""
    user_email = UserFactory.create(is_active=False).email if inactive else None

    with pytest.raises(CommandError, match="--user"):
        call_command("sync_backend_to_db", commit="abc123", user=user_email)

    mock_backend.assert_not_called()
