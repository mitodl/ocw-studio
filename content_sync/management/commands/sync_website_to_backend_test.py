"""Tests for the sync_website_to_backend management command."""  # noqa: INP001

import pytest
from django.core.management import CommandError, call_command

from users.factories import UserFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import Website

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_backend(mocker):
    """Replace the backend factory to avoid external calls."""
    return mocker.patch(
        "content_sync.management.commands.sync_website_to_backend.get_sync_backend"
    )


@pytest.mark.parametrize("actor", ["missing", "unknown", "inactive"])
def test_invalid_user_prevents_sync(mock_backend, actor):
    """Validate the actor before creating a repository, syncing, or deleting files."""
    website = WebsiteFactory.create()
    Website.objects.filter(pk=website.pk).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )
    options = {"filter": website.name, "force_create": True, "git_delete": True}
    if actor != "missing":
        options["user"] = "unknown@example.com"
    if actor == "inactive":
        options["user"] = UserFactory.create(is_active=False).email

    with pytest.raises(CommandError, match="--user"):
        call_command("sync_website_to_backend", **options)

    mock_backend.assert_not_called()
    website.refresh_from_db()
    assert website.has_unpublished_live is False
    assert website.has_unpublished_draft is False


@pytest.mark.parametrize("identifier", ["name", "short_id", "uuid", "title"])
@pytest.mark.parametrize("force_create", [True, False])
def test_actor_reaches_sync_and_deletion(mock_backend, identifier, force_create):
    """Existing site aliases work and both content and deletion commits use the actor."""
    actor = UserFactory.create()
    editor = UserFactory.create()
    content = WebsiteContentFactory.create(updated_by=editor)

    call_command(
        "sync_website_to_backend",
        filter=str(getattr(content.website, identifier)),
        user=actor.email,
        force_create=force_create,
        git_delete=True,
    )

    mock_backend.assert_called_once_with(content.website)
    backend = mock_backend.return_value
    assert backend.create_website_in_backend.call_count == int(force_create)
    backend.sync_all_content_to_backend.assert_called_once_with(commit_user=actor)
    backend.delete_orphaned_content_in_backend.assert_called_once_with(
        commit_user=actor
    )
    content.refresh_from_db()
    assert content.updated_by == editor


@pytest.mark.parametrize("identifier", ["name", "short_id"])
def test_excluded_website_is_not_synced(mock_backend, identifier):
    """Exclusions apply even when a website was selected through its UUID alias."""
    actor = UserFactory.create()
    selected = WebsiteFactory.create()
    excluded = WebsiteFactory.create()

    call_command(
        "sync_website_to_backend",
        filter=f"{selected.uuid},{excluded.uuid}",
        exclude=getattr(excluded, identifier),
        user=actor.email,
        git_delete=True,
    )

    mock_backend.assert_called_once_with(selected)


@pytest.mark.parametrize("supports_batch_commits", [True, False])
@pytest.mark.parametrize("batch_size", [None, 2])
def test_batch_options_preserve_commit_user(
    mock_backend, supports_batch_commits, batch_size
):
    """Batch options retain the operator on backends with or without batching."""
    actor = UserFactory.create()
    content = WebsiteContentFactory.create()
    backend = mock_backend.return_value
    backend.supports_batch_commits = supports_batch_commits

    call_command(
        "sync_website_to_backend",
        filter=content.website.name,
        user=actor.email,
        batch_commits=True,
        batch_size=batch_size,
        git_delete=True,
    )

    expected_kwargs = {"commit_user": actor}
    if supports_batch_commits:
        expected_kwargs["use_batch_commits"] = True
        if batch_size is not None:
            expected_kwargs["batch_size"] = batch_size
    backend.sync_all_content_to_backend.assert_called_once_with(**expected_kwargs)
    backend.delete_orphaned_content_in_backend.assert_called_once_with(
        commit_user=actor
    )
