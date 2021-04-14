""" Content sync model tests """
import pytest

from content_sync.models import ContentSyncState
from websites.factories import WebsiteContentFactory


@pytest.mark.parametrize(
    "current_checksum, synced_checksum, expected",
    [
        ["abc", "abc", True],
        ["abc", "abc1", False],
    ],
)
def test_contentsyncstate_is_synced(current_checksum, synced_checksum, expected):
    """ Verify ContentSyncState.is_synced returns True only if both checksums match """
    sync_state = ContentSyncState(
        current_checksum=current_checksum,
        synced_checksum=synced_checksum,
    )

    assert sync_state.is_synced is expected


@pytest.mark.django_db
def test_contentsyncstate_mark_synced():
    """ Verify ContentSyncState.mark_synced() updates the synced_checksum to the current one """
    content = WebsiteContentFactory.create()

    sync_state = content.content_sync_state
    sync_state.current_checksum = "abc"
    sync_state.calculate_checksum = "def"
    sync_state.mark_synced()

    assert sync_state.current_checksum == sync_state.synced_checksum
