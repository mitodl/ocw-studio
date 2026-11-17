"""Tests for the sync_unsynced_repos_to_backend management command."""  # noqa: INP001

import pytest
from django.core.management import CommandError, call_command

from users.factories import UserFactory
from websites.factories import WebsiteContentFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_backend(mocker):
    """Mock the backend factory."""
    return mocker.patch(
        "content_sync.management.commands.sync_unsynced_repos_to_backend.get_sync_backend"
    )


@pytest.mark.parametrize("supports_batch_commits", [True, False])
def test_sync_passes_commit_user(mock_backend, supports_batch_commits):
    """Forward the operator identity alongside supported batch options."""
    user = UserFactory.create()
    content = WebsiteContentFactory.create()
    backend = mock_backend.return_value
    backend.supports_batch_commits = supports_batch_commits

    call_command(
        "sync_unsynced_repos_to_backend",
        user=user.email,
        batch_commits=True,
        batch_size=2,
    )

    mock_backend.assert_called_once_with(content.website)
    backend.create_website_in_backend.assert_called_once_with()
    expected = {"commit_user": user}
    if supports_batch_commits:
        expected.update(use_batch_commits=True, batch_size=2)
    backend.sync_all_content_to_backend.assert_called_once_with(**expected)


@pytest.mark.parametrize("inactive", [True, False])
def test_sync_requires_active_user(mock_backend, inactive):
    """Reject inactive or missing users before using the backend."""
    options = {}
    if inactive:
        options["user"] = UserFactory.create(is_active=False).email

    with pytest.raises(CommandError, match="--user"):
        call_command("sync_unsynced_repos_to_backend", **options)

    mock_backend.assert_not_called()
