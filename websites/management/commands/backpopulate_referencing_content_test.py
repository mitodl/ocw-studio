"""Tests for backpopulate_referencing_content management command"""  # noqa: INP001

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase

from websites.constants import (
    CONTENT_TYPE_COURSE_COLLECTION,
    CONTENT_TYPE_HOMEPAGE_SETTINGS,
    CONTENT_TYPE_INSTRUCTOR,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_PROMO,
    CONTENT_TYPE_RESOURCE,
    CONTENT_TYPE_RESOURCE_LIST,
    CONTENT_TYPE_STORY,
    CONTENT_TYPE_TESTIMONIAL,
    CONTENT_TYPE_VIDEO_GALLERY,
)
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


@pytest.fixture
def ocw_www():
    """Create the ocw-www website fixture."""
    return WebsiteFactory.create(name="ocw-www")


@pytest.fixture
def course_website():
    """Create a course website fixture."""
    return WebsiteFactory.create()


@pytest.fixture
def instructors(ocw_www):
    """Create instructor content fixtures on ocw-www."""
    return [
        WebsiteContentFactory.create(
            website=ocw_www,
            type=CONTENT_TYPE_INSTRUCTOR,
            title="Dr. Test Instructor",
        ),
        WebsiteContentFactory.create(
            website=ocw_www,
            type=CONTENT_TYPE_INSTRUCTOR,
            title="Prof. Another Instructor",
        ),
    ]


@pytest.fixture
def sitemetadata_with_instructors(course_website, instructors):
    """Create sitemetadata that references instructor content."""
    return WebsiteContentFactory.create(
        website=course_website,
        type=CONTENT_TYPE_METADATA,
        metadata={
            "course_title": "Test Course",
            "course_description": "A test course description",
            "instructors": {
                "content": [i.text_id for i in instructors],
                "website": "ocw-www",
            },
        },
    )


def test_instructor_references_detected(sitemetadata_with_instructors, instructors):
    """Test that instructor UUIDs in sitemetadata are detected as references"""
    assert sitemetadata_with_instructors.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    sitemetadata_with_instructors.refresh_from_db()
    referenced_content = list(sitemetadata_with_instructors.referenced_by.all())

    assert len(referenced_content) == 2
    for instructor in instructors:
        assert instructor in referenced_content


def test_instructor_references_with_website_filter(
    course_website, sitemetadata_with_instructors, instructors
):
    """Test that sitemetadata correctly processes instructor refs with website filter"""
    call_command(
        "backpopulate_referencing_content",
        verbosity=0,
        filter=course_website.name,
    )

    sitemetadata_with_instructors.refresh_from_db()
    referenced_content = list(sitemetadata_with_instructors.referenced_by.all())

    assert len(referenced_content) == 2
    for instructor in instructors:
        assert instructor in referenced_content


@pytest.mark.django_db
def test_course_image_references_detected():
    """Test that course image fields in sitemetadata are detected as references."""
    website = WebsiteFactory.create()
    image_resource = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    image_thumbnail_resource = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    sitemetadata = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_METADATA,
        metadata={
            "course_description": "No references here",
            "course_image": {
                "content": image_resource.text_id,
                "website": website.name,
            },
            "course_image_thumbnail": {
                "content": image_thumbnail_resource.text_id,
                "website": website.name,
            },
        },
    )

    assert sitemetadata.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    sitemetadata.refresh_from_db()
    referenced_content = list(sitemetadata.referenced_by.all())
    assert len(referenced_content) == 2
    assert image_resource in referenced_content
    assert image_thumbnail_resource in referenced_content


@pytest.mark.django_db
def test_video_gallery_references_detected():
    """Test that video UUIDs in video_gallery metadata are detected as references"""
    website = WebsiteFactory.create()
    video1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    video2 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    video_gallery = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_VIDEO_GALLERY,
        metadata={
            "videos": {
                "content": [video1.text_id, video2.text_id],
                "website": website.name,
            },
        },
    )

    assert video_gallery.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    video_gallery.refresh_from_db()
    referenced_content = list(video_gallery.referenced_by.all())
    assert len(referenced_content) == 2
    assert video1 in referenced_content
    assert video2 in referenced_content


@pytest.mark.django_db
def test_resource_list_resources_references_detected():
    """Test that resource UUIDs in resource_list metadata are detected as references"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    resource2 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    resource_list = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE_LIST,
        metadata={
            "description": "No references here",
            "resources": {
                "content": [resource1.text_id, resource2.text_id],
                "website": website.name,
            },
        },
    )

    assert resource_list.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    resource_list.refresh_from_db()
    referenced_content = list(resource_list.referenced_by.all())
    assert len(referenced_content) == 2
    assert resource1 in referenced_content
    assert resource2 in referenced_content


@pytest.mark.django_db
def test_page_with_embedded_href_uuid_references_detected():
    """Test that href_uuid in embedded resources are detected as references"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    resource2 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    page = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_PAGE,
        markdown=(
            f'{{{{< resource uuid="{resource1.text_id}" '
            f'href_uuid="{resource2.text_id}" >}}}}'
        ),
    )

    assert page.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    page.refresh_from_db()
    referenced_content = list(page.referenced_by.all())
    assert len(referenced_content) == 2
    assert resource1 in referenced_content
    assert resource2 in referenced_content


@pytest.mark.django_db
def test_course_collection_references_detected():
    """Test that course-collection cover-image and courselists are detected"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    course_list1 = WebsiteContentFactory.create(
        website=website,
        type="course-lists",
    )
    course_list2 = WebsiteContentFactory.create(
        website=website,
        type="course-lists",
    )
    course_collection = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_COURSE_COLLECTION,
        metadata={
            "title": "My Collection",
            "cover-image": {"content": resource1.text_id},
            "courselists": {"content": [course_list1.text_id, course_list2.text_id]},
        },
    )

    assert course_collection.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    course_collection.refresh_from_db()
    referenced_content = list(course_collection.referenced_by.all())
    assert len(referenced_content) == 3
    assert resource1 in referenced_content
    assert course_list1 in referenced_content
    assert course_list2 in referenced_content


@pytest.mark.django_db
def test_promo_references_detected():
    """Test that promo image field is detected as a reference"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    promo = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_PROMO,
        metadata={
            "title": "Special Promo",
            "image": {"content": resource1.text_id},
        },
    )

    assert promo.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    promo.refresh_from_db()
    referenced_content = list(promo.referenced_by.all())
    assert len(referenced_content) == 1
    assert resource1 in referenced_content


@pytest.mark.django_db
def test_story_references_detected():
    """Test that story image field and markdown references are detected."""
    website = WebsiteFactory.create()
    image_resource = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    markdown_resource = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    story = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_STORY,
        markdown=f"Story body {{{{< resource {markdown_resource.text_id} >}}}}",
        metadata={
            "title": "Story",
            "image": {"content": image_resource.text_id},
        },
    )

    assert story.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    story.refresh_from_db()
    referenced_content = list(story.referenced_by.all())
    assert len(referenced_content) == 2
    assert image_resource in referenced_content
    assert markdown_resource in referenced_content


@pytest.mark.django_db
def test_ocw_www_featured_promos_and_stories_references_detected():
    """Test featured promos/stories on ocw-www homepage_settings are detected."""
    ocw_www = WebsiteFactory.create(name="ocw-www")
    promo = WebsiteContentFactory.create(
        website=ocw_www,
        type=CONTENT_TYPE_PROMO,
    )
    story = WebsiteContentFactory.create(
        website=ocw_www,
        type=CONTENT_TYPE_STORY,
    )
    homepage_settings = WebsiteContentFactory.create(
        website=ocw_www,
        type=CONTENT_TYPE_HOMEPAGE_SETTINGS,
        metadata={
            "featured_promos": {
                "content": [promo.text_id],
                "website": ocw_www.name,
            },
            "featured_stories": {
                "content": [story.text_id],
                "website": ocw_www.name,
            },
        },
    )

    assert homepage_settings.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    homepage_settings.refresh_from_db()
    referenced_content = list(homepage_settings.referenced_by.all())
    assert len(referenced_content) == 2
    assert promo in referenced_content
    assert story in referenced_content


@pytest.mark.django_db
def test_testimonial_references_detected():
    """Test that testimonial image field is detected as a reference"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    testimonial = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_TESTIMONIAL,
        metadata={
            "title": "John Doe",
            "image": {"content": resource1.text_id},
        },
    )

    assert testimonial.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    testimonial.refresh_from_db()
    referenced_content = list(testimonial.referenced_by.all())
    assert len(referenced_content) == 1
    assert resource1 in referenced_content


@pytest.mark.django_db
def test_testimonial_with_markdown_references():
    """Test testimonial with both image field and markdown references"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    resource2 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    testimonial = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_TESTIMONIAL,
        markdown=f"Testimonial text {{{{< resource {resource2.text_id} >}}}}",
        metadata={
            "title": "Jane Smith",
            "image": {"content": resource1.text_id},
        },
    )

    assert testimonial.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    testimonial.refresh_from_db()
    referenced_content = list(testimonial.referenced_by.all())
    assert len(referenced_content) == 2
    assert resource1 in referenced_content
    assert resource2 in referenced_content


@pytest.mark.django_db
def test_course_collection_with_description_markdown():
    """Test course-collection with description field containing resource links"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    resource2 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    course_list = WebsiteContentFactory.create(
        website=website,
        type="course-lists",
    )
    course_collection = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_COURSE_COLLECTION,
        markdown=f"Intro {{{{< resource {resource1.text_id} >}}}}",
        metadata={
            "title": "Collection with Description",
            "description": f"Description {{{{< resource {resource2.text_id} >}}}}",
            "courselists": {"content": [course_list.text_id]},
        },
    )

    assert course_collection.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    course_collection.refresh_from_db()
    referenced_content = list(course_collection.referenced_by.all())
    assert len(referenced_content) == 3
    assert resource1 in referenced_content
    assert resource2 in referenced_content
    assert course_list in referenced_content


@pytest.mark.django_db
def test_promo_with_markdown_references():
    """Test promo with both image field and markdown references"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    resource2 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    promo = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_PROMO,
        markdown=f"Promo content {{{{< resource {resource2.text_id} >}}}}",
        metadata={
            "title": "Special Promo",
            "image": {"content": resource1.text_id},
        },
    )

    assert promo.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    promo.refresh_from_db()
    referenced_content = list(promo.referenced_by.all())
    assert len(referenced_content) == 2
    assert resource1 in referenced_content
    assert resource2 in referenced_content


@pytest.mark.django_db
def test_course_collection_empty_courselists():
    """Test course-collection with empty courselists still populates cover-image"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    course_collection = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_COURSE_COLLECTION,
        metadata={
            "title": "Empty Collection",
            "cover-image": {"content": resource1.text_id},
            "courselists": {"content": []},
        },
    )

    assert course_collection.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    course_collection.refresh_from_db()
    referenced_content = list(course_collection.referenced_by.all())
    assert len(referenced_content) == 1
    assert resource1 in referenced_content


@pytest.mark.django_db
def test_testimonial_no_image_only_markdown():
    """Test testimonial with only markdown references, no image field"""
    website = WebsiteFactory.create()
    resource1 = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
    )
    testimonial = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_TESTIMONIAL,
        markdown=f"{{{{< resource {resource1.text_id} >}}}}",
        metadata={
            "title": "Bob Johnson",
        },
    )

    assert testimonial.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    testimonial.refresh_from_db()
    referenced_content = list(testimonial.referenced_by.all())
    assert len(referenced_content) == 1
    assert resource1 in referenced_content


@pytest.mark.django_db
def test_promo_no_image_field():
    """Test promo with no image field doesn't create references"""
    website = WebsiteFactory.create()
    promo = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_PROMO,
        metadata={
            "title": "Promo without Image",
            "description": "Just text",
        },
    )

    assert promo.referenced_by.count() == 0

    call_command("backpopulate_referencing_content", verbosity=0, stdout=StringIO())

    promo.refresh_from_db()
    # Should still be 0 since there are no references
    assert promo.referenced_by.count() == 0
