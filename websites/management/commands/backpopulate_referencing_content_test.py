"""Tests for backpopulate_referencing_content management command"""  # noqa: INP001

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase

from websites.constants import CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.backpopulate_referencing_content import Command

pytestmark = pytest.mark.django_db


class BackpopulateReferencingContentCommandTest(TestCase):
    """Test class for backpopulate_referencing_content management command"""

    def setUp(self):
        """Set up test data"""
        self.website1 = WebsiteFactory.create()
        self.website2 = WebsiteFactory.create()

        # Create content with references
        self.content1 = WebsiteContentFactory.create(
            website=self.website1,
            type=CONTENT_TYPE_PAGE,
            markdown='Link to {{% resource_link "550e8400-e29b-41d4-a716-446655440001" "Resource 1" %}}',
        )
        self.content2 = WebsiteContentFactory.create(
            website=self.website1,
            type=CONTENT_TYPE_RESOURCE,
            text_id="550e8400-e29b-41d4-a716-446655440001",
        )
        self.content3 = WebsiteContentFactory.create(
            website=self.website2,
            type=CONTENT_TYPE_PAGE,
            markdown='{{< resource uuid="550e8400-e29b-41d4-a716-446655440002" >}}',
        )
        self.content4 = WebsiteContentFactory.create(
            website=self.website2,
            type=CONTENT_TYPE_RESOURCE,
            text_id="550e8400-e29b-41d4-a716-446655440002",
        )

    @patch(
        "websites.management.commands.backpopulate_referencing_content.compile_referencing_content"
    )
    def test_collect_references(self, mock_compile):
        """Test _collect_references method"""
        command = Command()

        # Mock compile_referencing_content to return references
        mock_compile.side_effect = [
            ["550e8400-e29b-41d4-a716-446655440001"],
            [],
            ["550e8400-e29b-41d4-a716-446655440002"],
        ]

        content_batch = [self.content1, self.content2, self.content3]
        content_references, all_reference_uuids = command._collect_references(  # noqa: SLF001
            content_batch, verbosity=0
        )

        expected_references = {
            self.content1.id: ["550e8400-e29b-41d4-a716-446655440001"],
            self.content3.id: ["550e8400-e29b-41d4-a716-446655440002"],
        }
        expected_uuids = {
            "550e8400-e29b-41d4-a716-446655440001",
            "550e8400-e29b-41d4-a716-446655440002",
        }

        assert content_references == expected_references
        assert all_reference_uuids == expected_uuids

    def test_fetch_referenced_content(self):
        """Test _fetch_referenced_content method"""
        command = Command()

        reference_uuids = [self.content2.text_id, self.content4.text_id]
        referenced_content_map = command._fetch_referenced_content(  # noqa: SLF001
            reference_uuids, verbosity=0
        )

        assert len(referenced_content_map) == 2
        assert referenced_content_map[self.content2.text_id].id == self.content2.id
        assert referenced_content_map[self.content4.text_id].id == self.content4.id

    def test_update_relationships(self):
        """Test _update_relationships method"""
        command = Command()

        content_references = {
            self.content1.id: [self.content2.text_id],
            self.content3.id: [self.content4.text_id],
        }
        referenced_content_map = {
            self.content2.text_id: self.content2,
            self.content4.text_id: self.content4,
        }

        batch_updated = command._update_relationships(  # noqa: SLF001
            content_references, referenced_content_map, verbosity=0
        )

        assert batch_updated == 2

        # Verify relationships were set
        self.content1.refresh_from_db()
        self.content3.refresh_from_db()

        assert list(self.content1.referenced_by.all()) == [self.content2]
        assert list(self.content3.referenced_by.all()) == [self.content4]

    def test_update_relationships_missing_content(self):
        """Test _update_relationships handles missing content gracefully"""
        command = Command()

        # Use non-existent content ID
        content_references = {999999: ["550e8400-e29b-41d4-a716-446655440001"]}
        referenced_content_map = {"550e8400-e29b-41d4-a716-446655440001": self.content2}

        batch_updated = command._update_relationships(  # noqa: SLF001
            content_references, referenced_content_map, verbosity=0
        )

        assert batch_updated == 0

    @patch(
        "websites.management.commands.backpopulate_referencing_content.compile_referencing_content"
    )
    def test_process_batch(self, mock_compile):
        """Test _process_batch method"""
        command = Command()

        # Mock compile_referencing_content
        mock_compile.side_effect = [
            [self.content2.text_id],
            [],
        ]

        website_qset = [self.website1]
        batch_updated = command._process_batch(website_qset, 0, 10, verbosity=0)  # noqa: SLF001

        assert batch_updated == 1

        # Verify the relationship was set
        self.content1.refresh_from_db()
        assert list(self.content1.referenced_by.all()) == [self.content2]

    def test_process_batch_no_references(self):
        """Test _process_batch when no references are found"""
        command = Command()

        with patch(
            "websites.management.commands.backpopulate_referencing_content.compile_referencing_content"
        ) as mock_compile:
            mock_compile.return_value = []

            website_qset = [self.website1]
            batch_updated = command._process_batch(website_qset, 0, 10, verbosity=0)  # noqa: SLF001

            assert batch_updated == 0

    def test_empty_content_batch(self):
        """Test handling of empty content batch"""
        command = Command()

        content_references, all_reference_uuids = command._collect_references(  # noqa: SLF001
            [], verbosity=0
        )

        assert content_references == {}
        assert all_reference_uuids == set()

    def test_update_relationships_empty_references(self):
        """Test _update_relationships with empty references"""
        command = Command()

        batch_updated = command._update_relationships({}, {}, verbosity=0)  # noqa: SLF001

        assert batch_updated == 0


class BackpopulateReferencingContentCommandIntegrationTest(TestCase):
    """Integration tests for the management command"""

    def setUp(self):
        """Set up test data"""
        self.website = WebsiteFactory.create()

        # Create content that references each other
        self.resource1 = WebsiteContentFactory.create(
            website=self.website,
            type=CONTENT_TYPE_RESOURCE,
            text_id="550e8400-e29b-41d4-a716-446655440001",
        )
        self.resource2 = WebsiteContentFactory.create(
            website=self.website,
            type=CONTENT_TYPE_RESOURCE,
            text_id="550e8400-e29b-41d4-a716-446655440002",
        )
        self.page = WebsiteContentFactory.create(
            website=self.website,
            type=CONTENT_TYPE_PAGE,
            markdown=(
                f"This page references "
                f'{{{{% resource_link "{self.resource1.text_id}" "Resource 1" %}}}} '
                f'and {{{{< resource uuid="{self.resource2.text_id}" >}}}}'
            ),
        )

    def test_end_to_end_execution(self):
        """Test end-to-end execution of the command"""
        # Ensure no references exist initially
        assert self.page.referenced_by.count() == 0

        # Run the command
        out = StringIO()
        call_command(
            "backpopulate_referencing_content",
            verbosity=0,
            stdout=out,
        )

        # Check that references were populated
        self.page.refresh_from_db()
        referenced_content = list(self.page.referenced_by.all())

        assert len(referenced_content) == 2
        assert self.resource1 in referenced_content
        assert self.resource2 in referenced_content

    def test_multiple_batches(self):
        """Test command execution with multiple batches"""
        # Create additional content to force multiple batches
        for _ in range(5):
            WebsiteContentFactory.create(website=self.website, type=CONTENT_TYPE_PAGE)

        # Run the command with small batch size to force multiple batches
        call_command(
            "backpopulate_referencing_content",
            verbosity=0,
            batch_size=2,
        )

        # Verify the original references were still populated correctly
        self.page.refresh_from_db()
        referenced_content = list(self.page.referenced_by.all())

        assert len(referenced_content) == 2
        assert self.resource1 in referenced_content
        assert self.resource2 in referenced_content
