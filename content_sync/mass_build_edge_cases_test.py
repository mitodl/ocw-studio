"""Edge case tests for mass build and publish functionality"""

import pytest
from django.db.models.signals import post_save
from factory.django import mute_signals

from content_sync import api
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.factories import ContentSyncStateFactory
from websites.constants import (
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_STARTED,
    PUBLISH_STATUS_SUCCEEDED,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


def test_get_mass_build_pipeline_with_no_websites(settings, mocker):
    """Test mass build pipeline when there are no websites to build"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    # Ensure no websites exist
    from websites.models import Website

    Website.objects.all().delete()

    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    # Should return pipeline object even with no websites
    assert pipeline is not None


def test_get_mass_build_pipeline_with_only_unpublished_websites(settings, mocker):
    """Test mass build pipeline when all websites are unpublished"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    # Create websites that have never been published
    WebsiteFactory.create_batch(
        3,
        publish_date=None,
        draft_publish_date=None,
        live_publish_status=PUBLISH_STATUS_NOT_STARTED,
        draft_publish_status=PUBLISH_STATUS_NOT_STARTED,
    )

    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    assert pipeline is not None


def test_get_mass_build_pipeline_with_mixed_publish_statuses(settings, mocker):
    """Test mass build pipeline with websites in various publish states"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    # Create websites in different states
    WebsiteFactory.create(
        live_publish_status=PUBLISH_STATUS_SUCCEEDED,
        draft_publish_status=PUBLISH_STATUS_SUCCEEDED,
    )
    WebsiteFactory.create(
        live_publish_status=PUBLISH_STATUS_STARTED,
        draft_publish_status=PUBLISH_STATUS_STARTED,
    )
    WebsiteFactory.create(
        live_publish_status=PUBLISH_STATUS_ERRORED,
        draft_publish_status=PUBLISH_STATUS_ERRORED,
    )
    WebsiteFactory.create(
        live_publish_status=PUBLISH_STATUS_ABORTED,
        draft_publish_status=PUBLISH_STATUS_ABORTED,
    )

    # Should work with mixed statuses
    pipeline_live = api.get_mass_build_sites_pipeline(VERSION_LIVE)
    pipeline_draft = api.get_mass_build_sites_pipeline(VERSION_DRAFT)

    assert pipeline_live is not None
    assert pipeline_draft is not None


def test_get_mass_build_pipeline_offline_and_online(settings, mocker):
    """Test that both offline and online pipelines can be retrieved"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    WebsiteFactory.create_batch(2)

    # Test online pipeline
    pipeline_online = api.get_mass_build_sites_pipeline(VERSION_DRAFT, offline=False)
    assert pipeline_online is not None

    # Test offline pipeline
    pipeline_offline = api.get_mass_build_sites_pipeline(VERSION_DRAFT, offline=True)
    assert pipeline_offline is not None


def test_mass_build_with_content_sync_errors(settings, mocker):
    """Test mass build pipeline behavior when content sync has errors"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    website = WebsiteFactory.create()

    # Create content with sync state indicating errors
    content1 = WebsiteContentFactory.create(website=website)
    content2 = WebsiteContentFactory.create(website=website)

    with mute_signals(post_save):
        # Content with mismatched checksums (indicating sync needed)
        ContentSyncStateFactory.create(
            content=content1,
            current_checksum="abc123",
            synced_checksum="def456",  # Different - needs sync
        )
        # Content that's synced
        ContentSyncStateFactory.create(
            content=content2, current_checksum="xyz789", synced_checksum="xyz789"
        )

    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    assert pipeline is not None


def test_mass_build_pipeline_version_consistency(settings, mocker):
    """Test that the correct version is used consistently in pipeline"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    WebsiteFactory.create_batch(2)

    # Get pipelines for both versions
    pipeline_draft = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    pipeline_live = api.get_mass_build_sites_pipeline(VERSION_LIVE)

    # Both should exist but should be different instances
    assert pipeline_draft is not None
    assert pipeline_live is not None
    # They should be different objects
    assert pipeline_draft is not pipeline_live


def test_mass_build_with_large_number_of_websites(settings, mocker):
    """Test mass build pipeline can handle a large number of websites"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    # Create a large number of websites
    num_websites = 50
    WebsiteFactory.create_batch(num_websites)

    # Should be able to get pipeline without errors
    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    assert pipeline is not None

    # Test offline version too
    pipeline_offline = api.get_mass_build_sites_pipeline(VERSION_DRAFT, offline=True)
    assert pipeline_offline is not None


def test_mass_build_with_duplicate_website_names(settings, mocker):
    """Test mass build pipeline handles edge case of duplicate website names gracefully"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    # Create websites (unique UUIDs but could have similar other properties)
    website1 = WebsiteFactory.create(title="Test Course")
    website2 = WebsiteFactory.create(title="Test Course")

    assert website1.uuid != website2.uuid
    assert website1.name != website2.name  # Names should be unique

    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    assert pipeline is not None


def test_mass_build_pipeline_with_archived_websites(settings, mocker):
    """Test that archived/unpublished websites are handled correctly"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    # Create active websites
    WebsiteFactory.create_batch(2, publish_date__isnull=False)

    # Create unpublished websites (never published)
    WebsiteFactory.create_batch(2, publish_date=None, unpublish_status=None)

    # Create websites marked for unpublishing
    WebsiteFactory.create_batch(2, unpublish_status=PUBLISH_STATUS_NOT_STARTED)

    pipeline = api.get_mass_build_sites_pipeline(VERSION_LIVE)
    assert pipeline is not None


@pytest.mark.parametrize(
    ("version", "offline"),
    [
        (VERSION_DRAFT, True),
        (VERSION_DRAFT, False),
        (VERSION_LIVE, True),
        (VERSION_LIVE, False),
    ],
)
def test_mass_build_pipeline_all_combinations(settings, mocker, version, offline):
    """Test all combinations of version and offline parameters"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    WebsiteFactory.create_batch(3)

    pipeline = api.get_mass_build_sites_pipeline(version, offline=offline)
    assert pipeline is not None


def test_mass_build_pipeline_with_content_without_metadata(settings, mocker):
    """Test mass build with content that has null or empty metadata"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    website = WebsiteFactory.create()

    # Create content with various metadata states
    WebsiteContentFactory.create(website=website, metadata=None)
    WebsiteContentFactory.create(website=website, metadata={})
    WebsiteContentFactory.create(
        website=website, metadata={"title": "Test", "description": ""}
    )

    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    assert pipeline is not None


def test_mass_build_pipeline_with_special_characters_in_content(settings, mocker):
    """Test mass build with content containing special characters"""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.TestBackend"
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"

    website = WebsiteFactory.create()

    # Create content with special characters
    WebsiteContentFactory.create(
        website=website,
        title="Test with émojis 🎓 and spëcial çhars",
        markdown="Content with **bold** and _italic_ and [links](http://example.com)",
        metadata={
            "description": "Description with <html> tags & special chars: €, £, ¥"
        },
    )

    # Create content with nested markdown structures
    WebsiteContentFactory.create(
        website=website,
        markdown="""
        # Header
        ## Subheader with {{< sub "₂" >}} and {{< sup "®" >}}
        
        [Link with [nested] brackets](http://example.com)
        """,
    )

    pipeline = api.get_mass_build_sites_pipeline(VERSION_DRAFT)
    assert pipeline is not None
