"""Tests for external_resources.models"""

import pytest
from django.db import IntegrityError
from mitol.common.utils import now_in_utc

from external_resources.factories import ExternalResourceStateFactory
from external_resources.models import ExternalResourceState
from websites.factories import WebsiteContentFactory


pytestmark = pytest.mark.django_db


class TestExternalResourceState:
    """Tests for ExternalResourceState model"""

    def test_external_resource_state_creation(self):
        """Test creating an ExternalResourceState instance"""
        content = WebsiteContentFactory.create()
        state = ExternalResourceState.objects.create(
            content=content,
            status=ExternalResourceState.Status.VALID,
            external_url_response_code=200,
        )
        
        assert state.content == content
        assert state.status == ExternalResourceState.Status.VALID
        assert state.external_url_response_code == 200
        assert state.last_checked is None  # Default
        assert state.wayback_status == ExternalResourceState.WaybackStatus.PENDING  # Default

    def test_external_resource_state_str_representation(self):
        """Test string representation of ExternalResourceState"""
        state = ExternalResourceStateFactory.build()
        str_repr = str(state)
        # The string representation should contain meaningful information
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0

    def test_external_resource_state_default_values(self):
        """Test default values for ExternalResourceState fields"""
        content = WebsiteContentFactory.create()
        state = ExternalResourceState.objects.create(content=content)
        
        assert state.status == ExternalResourceState.Status.UNCHECKED
        assert state.wayback_status == ExternalResourceState.WaybackStatus.PENDING
        assert state.last_checked is None
        assert state.external_url_response_code is None
        assert state.wayback_job_id is None
        assert state.wayback_url is None
        assert state.wayback_status_ext is None
        assert state.wayback_http_status is None
        assert state.wayback_last_successful_submission is None

    def test_external_resource_state_status_choices(self):
        """Test all status choices are valid"""
        content = WebsiteContentFactory.create()
        
        for status_value, _ in ExternalResourceState.Status.choices:
            state = ExternalResourceState.objects.create(
                content=content, status=status_value
            )
            assert state.status == status_value
            state.delete()

    def test_external_resource_state_wayback_status_choices(self):
        """Test all wayback status choices are valid"""
        content = WebsiteContentFactory.create()
        
        for wayback_status_value, _ in ExternalResourceState.WaybackStatus.choices:
            state = ExternalResourceState.objects.create(
                content=content, wayback_status=wayback_status_value
            )
            assert state.wayback_status == wayback_status_value
            state.delete()

    def test_external_resource_state_one_to_one_relationship(self):
        """Test one-to-one relationship with WebsiteContent"""
        content = WebsiteContentFactory.create()
        state = ExternalResourceState.objects.create(content=content)
        
        # Test reverse relationship
        assert content.external_resource_state == state
        
        # Test that creating another state for the same content raises an error
        with pytest.raises(IntegrityError):
            ExternalResourceState.objects.create(content=content)

    def test_external_resource_state_cascade_delete(self):
        """Test that deleting content also deletes the state"""
        content = WebsiteContentFactory.create()
        state = ExternalResourceState.objects.create(content=content)
        state_id = state.id
        
        content.delete()
        
        # State should be deleted as well due to CASCADE
        assert not ExternalResourceState.objects.filter(id=state_id).exists()

    def test_external_resource_state_timestamped_model(self):
        """Test that ExternalResourceState inherits from TimestampedModel"""
        state = ExternalResourceStateFactory.create()
        
        assert hasattr(state, "created_on")
        assert hasattr(state, "updated_on")
        assert state.created_on is not None
        assert state.updated_on is not None

    @pytest.mark.parametrize(
        ("status", "expected_label"),
        [
            (ExternalResourceState.Status.UNCHECKED, "Unchecked or pending check"),
            (ExternalResourceState.Status.VALID, "External Resource URL is valid"),
            (ExternalResourceState.Status.BROKEN, "External Resource URL is broken"),
            (
                ExternalResourceState.Status.CHECK_FAILED,
                "Last attempt to check the External Resource URL failed",
            ),
        ],
    )
    def test_external_resource_state_status_labels(self, status, expected_label):
        """Test that status choices have correct labels"""
        assert status.label == expected_label

    @pytest.mark.parametrize(
        ("wayback_status", "expected_label"),
        [
            (ExternalResourceState.WaybackStatus.PENDING, "Pending"),
            (ExternalResourceState.WaybackStatus.SUCCESS, "Success"),
            (ExternalResourceState.WaybackStatus.ERROR, "Error"),
        ],
    )
    def test_external_resource_wayback_status_labels(self, wayback_status, expected_label):
        """Test that wayback status choices have correct labels"""
        assert wayback_status.label == expected_label

    def test_external_resource_state_bulk_update_or_create_manager(self):
        """Test that the model uses BulkUpdateOrCreateQuerySet manager"""
        # This tests that the objects manager has the bulk_update_or_create method
        assert hasattr(ExternalResourceState.objects, "bulk_update_or_create")

    def test_external_resource_state_help_text(self):
        """Test field help text"""
        status_field = ExternalResourceState._meta.get_field("status")
        assert status_field.help_text == "Status of the external resource (valid, broken, etc.)."
        
        last_checked_field = ExternalResourceState._meta.get_field("last_checked")
        assert last_checked_field.help_text == "The last time when this resource was checked for breakages."

    def test_external_resource_state_field_constraints(self):
        """Test field constraints and properties"""
        status_field = ExternalResourceState._meta.get_field("status")
        assert status_field.max_length == 16
        assert status_field.default == ExternalResourceState.Status.UNCHECKED
        
        last_checked_field = ExternalResourceState._meta.get_field("last_checked")
        assert last_checked_field.null is True
        assert last_checked_field.blank is True
        assert last_checked_field.default is None

    def test_external_resource_state_with_all_fields(self):
        """Test creating ExternalResourceState with all fields populated"""
        current_time = now_in_utc()
        content = WebsiteContentFactory.create()
        
        state = ExternalResourceState.objects.create(
            content=content,
            status=ExternalResourceState.Status.VALID,
            last_checked=current_time,
            external_url_response_code=200,
            wayback_job_id="test-job-123",
            wayback_status=ExternalResourceState.WaybackStatus.SUCCESS,
            wayback_url="https://web.archive.org/test",
            wayback_status_ext="Captured successfully",
            wayback_http_status=200,
            wayback_last_successful_submission=current_time,
        )
        
        assert state.status == ExternalResourceState.Status.VALID
        assert state.last_checked == current_time
        assert state.external_url_response_code == 200
        assert state.wayback_job_id == "test-job-123"
        assert state.wayback_status == ExternalResourceState.WaybackStatus.SUCCESS
        assert state.wayback_url == "https://web.archive.org/test"
        assert state.wayback_status_ext == "Captured successfully"
        assert state.wayback_http_status == 200
        assert state.wayback_last_successful_submission == current_time

    def test_external_resource_state_factory(self):
        """Test that the factory creates valid instances"""
        state = ExternalResourceStateFactory.create()
        
        assert isinstance(state, ExternalResourceState)
        assert state.content is not None
        assert state.status in [choice[0] for choice in ExternalResourceState.Status.choices]
        assert state.wayback_status in [choice[0] for choice in ExternalResourceState.WaybackStatus.choices]
        # Other fields should be populated by the factory
        assert state.external_url_response_code is not None
        assert state.wayback_job_id is not None
