""" Content sync api tests """
import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals

from content_sync.api import upsert_content_sync_state
from websites.factories import WebsiteContentFactory


pytestmark = pytest.mark.django_db


def test_upsert_content_sync_state_create():
    """ Verify that upsert_content_sync_state creates a ContentSyncState record for the content """
    with mute_signals(post_save):
        content = WebsiteContentFactory.create(markdown="abc")

    assert getattr(content, "content_sync_state", None) is None

    upsert_content_sync_state(content)

    content.refresh_from_db()

    abc_checksum = content.calculate_checksum()

    assert content.content_sync_state is not None
    assert content.content_sync_state.synced_checksum is None
    assert content.content_sync_state.current_checksum == abc_checksum


def test_upsert_content_sync_state_update():
    """ Verify that upsert_content_sync_state updates a ContentSyncState record for the content """
    content = WebsiteContentFactory.create(markdown="abc")

    abc_checksum = content.calculate_checksum()

    content.content_sync_state.mark_synced()
    content.markdown = "def"

    def_checksum = content.calculate_checksum()

    with mute_signals(post_save):
        content.save()

    upsert_content_sync_state(content)

    content.content_sync_state.refresh_from_db()
    assert content.content_sync_state.synced_checksum == abc_checksum
    assert content.content_sync_state.current_checksum == def_checksum
