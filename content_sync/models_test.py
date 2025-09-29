"""Content sync model tests"""

import pytest
from django.db import IntegrityError

from content_sync.factories import ContentSyncStateFactory
from content_sync.models import ContentSyncState
from websites.factories import WebsiteContentFactory


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("current_checksum", "synced_checksum", "expected"),
    [
        ["abc", "abc", True],  # noqa: PT007
        ["abc", "abc1", False],  # noqa: PT007
        [None, "abc", False],  # noqa: PT007
        ["abc", None, False],  # noqa: PT007
        [None, None, True],  # noqa: PT007
    ],
)
def test_contentsyncstate_is_synced(current_checksum, synced_checksum, expected):
    """Verify ContentSyncState.is_synced returns True only if both checksums match"""
    sync_state = ContentSyncState(
        current_checksum=current_checksum,
        synced_checksum=synced_checksum,
    )

    assert sync_state.is_synced is expected


class TestContentSyncState:
    """Tests for ContentSyncState model"""

    def test_contentsyncstate_creation(self):
        """Test creating a ContentSyncState instance"""
        content = WebsiteContentFactory.create()
        state = ContentSyncState.objects.create(
            content=content,
            current_checksum="abc123",
            synced_checksum="def456",
            data={"key": "value"},
        )
        
        assert state.content == content
        assert state.current_checksum == "abc123"
        assert state.synced_checksum == "def456"
        assert state.data == {"key": "value"}

    def test_contentsyncstate_str_representation(self):
        """Test string representation of ContentSyncState"""
        content = WebsiteContentFactory.create()
        state = ContentSyncState.objects.create(
            content=content,
            current_checksum="abc123",
        )
        str_repr = str(state)
        
        # Should contain meaningful information about the content
        assert isinstance(str_repr, str)
        assert "Sync State for content:" in str_repr
        assert content.title in str_repr if content.title else True

    def test_contentsyncstate_default_values(self):
        """Test default values for ContentSyncState fields"""
        content = WebsiteContentFactory.create()
        state = ContentSyncState.objects.create(
            content=content,
            current_checksum="abc123",
        )
        
        assert state.synced_checksum is None
        assert state.data is None

    def test_contentsyncstate_one_to_one_relationship(self):
        """Test one-to-one relationship with WebsiteContent"""
        content = WebsiteContentFactory.create()
        state = ContentSyncState.objects.create(
            content=content,
            current_checksum="abc123",
        )
        
        # Test reverse relationship
        assert content.content_sync_state == state
        
        # Test that creating another state for the same content raises an error
        with pytest.raises(IntegrityError):
            ContentSyncState.objects.create(
                content=content,
                current_checksum="def456",
            )

    def test_contentsyncstate_cascade_delete(self):
        """Test that deleting content also deletes the sync state"""
        content = WebsiteContentFactory.create()
        state = ContentSyncState.objects.create(
            content=content,
            current_checksum="abc123",
        )
        state_id = state.id
        
        content.delete()
        
        # State should be deleted as well due to CASCADE
        assert not ContentSyncState.objects.filter(id=state_id).exists()

    def test_contentsyncstate_timestamped_model(self):
        """Test that ContentSyncState inherits from TimestampedModel"""
        state = ContentSyncStateFactory.create()
        
        assert hasattr(state, "created_on")
        assert hasattr(state, "updated_on")
        assert state.created_on is not None
        assert state.updated_on is not None

    def test_contentsyncstate_bulk_update_or_create_manager(self):
        """Test that the model uses BulkUpdateOrCreateQuerySet manager"""
        # This tests that the objects manager has the bulk_update_or_create method
        assert hasattr(ContentSyncState.objects, "bulk_update_or_create")

    def test_contentsyncstate_checksum_field_constraints(self):
        """Test checksum field constraints"""
        current_checksum_field = ContentSyncState._meta.get_field("current_checksum")  # noqa: SLF001
        synced_checksum_field = ContentSyncState._meta.get_field("synced_checksum")  # noqa: SLF001
        
        # Both fields should have max_length of 64 (sized for SHA256)
        assert current_checksum_field.max_length == 64
        assert synced_checksum_field.max_length == 64
        
        # synced_checksum should be nullable, current_checksum should not
        assert current_checksum_field.null is False
        assert synced_checksum_field.null is True

    def test_contentsyncstate_data_field(self):
        """Test data field functionality"""
        content = WebsiteContentFactory.create()
        test_data = {
            "git_sha": "abc123def456",
            "last_sync_time": "2023-01-01T00:00:00Z",
            "sync_metadata": {"version": "1.0", "source": "github"},
        }
        
        state = ContentSyncState.objects.create(
            content=content,
            current_checksum="abc123",
            data=test_data,
        )
        
        # Reload from database to ensure JSON serialization/deserialization works
        state.refresh_from_db()
        assert state.data == test_data

    def test_contentsyncstate_factory(self):
        """Test that the factory creates valid instances"""
        state = ContentSyncStateFactory.create()
        
        assert isinstance(state, ContentSyncState)
        assert state.content is not None
        assert state.current_checksum is not None
        # Factory should create a valid checksum
        assert len(state.current_checksum) > 0

    @pytest.mark.parametrize(
        ("current", "synced", "expected_synced"),
        [
            ("abc123", "abc123", True),
            ("abc123", "def456", False),
            ("", "", True),
            ("abc", "", False),
            ("", "abc", False),
        ],
    )
    def test_contentsyncstate_is_synced_variations(self, current, synced, expected_synced):
        """Test is_synced property with various checksum combinations"""
        state = ContentSyncState(
            current_checksum=current,
            synced_checksum=synced,
        )
        assert state.is_synced is expected_synced
