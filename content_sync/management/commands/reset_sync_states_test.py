"""Tests for the reset_sync_states management command."""  # noqa: INP001

from types import SimpleNamespace

import pytest
from django.core.management import CommandError, call_command

from content_sync.models import ContentSyncState
from users.factories import UserFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def sync_mocks(mocker, settings):
    """Enable syncing with mocked backend and task entry points."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    command_module = "content_sync.management.commands.reset_sync_states"
    return SimpleNamespace(
        backend=mocker.patch(f"{command_module}.get_sync_backend"),
        task=mocker.patch(f"{command_module}.sync_unsynced_websites.delay"),
    )


@pytest.mark.parametrize("actor", ["missing", "unknown", "inactive"])
def test_invalid_user_prevents_reset(sync_mocks, actor):
    """When syncing, a missing or invalid actor must fail before resetting any state."""
    content = WebsiteContentFactory.create()
    ContentSyncState.objects.filter(content=content).update(
        synced_checksum="previous", data={"filepath": "previous.md"}
    )
    options = {"filter": content.website.name}
    if actor != "missing":
        options["user"] = "unknown@example.com"
    if actor == "inactive":
        options["user"] = UserFactory.create(is_active=False).email

    with pytest.raises(CommandError, match="--user"):
        call_command("reset_sync_states", **options)

    content.content_sync_state.refresh_from_db()
    assert content.content_sync_state.synced_checksum == "previous"
    assert content.content_sync_state.data == {"filepath": "previous.md"}
    sync_mocks.backend.assert_not_called()
    sync_mocks.task.assert_not_called()


@pytest.mark.parametrize("queued", [True, False])
def test_reset_and_sync_preserve_selected_scope(sync_mocks, queued):
    """All reset filters also limit actor-attributed sync, including dirty/deleted rows."""
    actor = UserFactory.create()
    editor = UserFactory.create()
    website = WebsiteFactory.create(source="studio")
    excluded_website = WebsiteFactory.create(starter=website.starter, source="studio")
    other_starter = WebsiteFactory.create(source="studio")
    other_source = WebsiteFactory.create(starter=website.starter, source="ocw-import")
    selected = WebsiteContentFactory.create_batch(
        3, website=website, type="page", updated_by=editor
    )
    selected[2].delete()
    unselected = [
        WebsiteContentFactory.create(website=website, type="resource"),
        WebsiteContentFactory.create(website=excluded_website, type="page"),
        WebsiteContentFactory.create(website=other_starter, type="page"),
        WebsiteContentFactory.create(website=other_source, type="page"),
    ]
    ContentSyncState.objects.all().update(
        synced_checksum="previous", data={"filepath": "previous.md"}
    )
    ContentSyncState.objects.filter(content=selected[1]).update(synced_checksum=None)
    options = {
        "user": actor.email,
        "type": "page",
        "starter": website.starter.slug,
        "source": "studio",
        "exclude": excluded_website.short_id,
    }
    if not queued:
        options["filter"] = ",".join(
            str(site.uuid)
            for site in [website, excluded_website, other_starter, other_source]
        )

    call_command("reset_sync_states", **options)

    expected_ids = {content.pk for content in selected}
    if queued:
        sync_mocks.backend.assert_not_called()
        sync_mocks.task.assert_called_once()
        task_options = sync_mocks.task.call_args.kwargs
        assert task_options["commit_user_id"] == actor.id
        assert task_options["create_backends"] is False
        assert set(task_options["content_ids"]) == expected_ids
    else:
        sync_mocks.task.assert_not_called()
        sync_mocks.backend.assert_called_once_with(website)
        sync = sync_mocks.backend.return_value.sync_all_content_to_backend
        sync.assert_called_once()
        assert sync.call_args.kwargs["commit_user"] == actor
        assert (
            set(sync.call_args.kwargs["query_set"].values_list("pk", flat=True))
            == expected_ids
        )
    for content in selected:
        content.refresh_from_db()
        content.content_sync_state.refresh_from_db()
        assert content.updated_by == editor
        assert content.content_sync_state.synced_checksum is None
    assert selected[0].content_sync_state.data is None
    assert selected[1].content_sync_state.data == {"filepath": "previous.md"}
    for content in unselected:
        content.content_sync_state.refresh_from_db()
        assert content.content_sync_state.synced_checksum == "previous"
        assert content.content_sync_state.data == {"filepath": "previous.md"}


@pytest.mark.parametrize("queued", [True, False])
def test_empty_scope_does_not_sync(sync_mocks, queued):
    """An empty content selection must not fall back to an unscoped sync."""
    actor = UserFactory.create()
    content = WebsiteContentFactory.create(type="resource")
    options = {"user": actor.email, "type": "page"}
    if not queued:
        options["filter"] = content.website.name

    call_command("reset_sync_states", **options)

    sync_mocks.backend.assert_not_called()
    sync_mocks.task.assert_not_called()


@pytest.mark.parametrize("skip_sync", [True, False])
def test_reset_without_sync_needs_no_user(sync_mocks, mocker, settings, skip_sync):
    """Without syncing, reset needs no user and does not load content IDs into memory."""
    if not skip_sync:
        settings.CONTENT_SYNC_BACKEND = None
    content = WebsiteContentFactory.create()
    ContentSyncState.objects.filter(content=content).update(
        synced_checksum="previous", data={"filepath": "previous.md"}
    )
    values_list = mocker.patch("django.db.models.query.QuerySet.values_list")

    call_command("reset_sync_states", skip_sync=skip_sync)

    values_list.assert_not_called()
    content.content_sync_state.refresh_from_db()
    assert content.content_sync_state.synced_checksum is None
    assert content.content_sync_state.data is None
    sync_mocks.backend.assert_not_called()
    sync_mocks.task.assert_not_called()


def test_unfiltered_sync_avoids_content_id_payload(sync_mocks, mocker):
    """An explicitly global reset can use the existing global sync task scope."""
    actor = UserFactory.create()
    WebsiteContentFactory.create()
    values_list = mocker.patch("django.db.models.query.QuerySet.values_list")

    call_command("reset_sync_states", user=actor.email)

    values_list.assert_not_called()
    sync_mocks.task.assert_called_once_with(
        create_backends=False, commit_user_id=actor.id, content_ids=None
    )
