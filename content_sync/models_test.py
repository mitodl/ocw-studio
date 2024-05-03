"""Content sync model tests"""

import pytest

from content_sync.models import ContentSyncState


@pytest.mark.parametrize(
    ("current_checksum", "synced_checksum", "expected"),
    [
        ["abc", "abc", True],  # noqa: PT007
        ["abc", "abc1", False],  # noqa: PT007
    ],
)
def test_contentsyncstate_is_synced(current_checksum, synced_checksum, expected):
    """Verify ContentSyncState.is_synced returns True only if both checksums match"""
    sync_state = ContentSyncState(
        current_checksum=current_checksum,
        synced_checksum=synced_checksum,
    )

    assert sync_state.is_synced is expected
