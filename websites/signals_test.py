"""Tests for signals"""

import pytest

from users.factories import UserFactory
from websites import constants
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.serializers import WebsiteContentDetailSerializer


@pytest.mark.django_db
def test_handle_website_save():
    """Groups should be created for a new Website"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    assert website.admin_group is not None
    assert website.editor_group is not None
    assert website.owner.has_perm(constants.PERMISSION_EDIT, website)


@pytest.mark.django_db
def test_navmenu_updated_on_page_title_change(mocker, enable_websitecontent_signal):
    """Navmenu pageRef and name are updated when a page's title changes"""
    website = WebsiteFactory.create(owner=UserFactory.create())

    page = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_PAGE,
        dirpath="",
        title="Original Title",
        filename="original-title",
        text_id="abc123",
    )
    navmenu = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_NAVMENU,
        metadata={
            constants.WEBSITE_CONTENT_LEFTNAV: [
                {
                    "identifier": "abc123",
                    "pageRef": "/pages/original-title",
                    "name": "Original Title",
                }
            ]
        },
    )

    page.title = "New Title"
    serializer = WebsiteContentDetailSerializer(
        instance=page, data={"title": "New Title"}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    navmenu.refresh_from_db()
    menu_item = navmenu.metadata[constants.WEBSITE_CONTENT_LEFTNAV][0]
    assert menu_item["pageRef"] == "/pages/new-title"
    assert menu_item["name"] == "New Title"


@pytest.mark.django_db
def test_populate_course_list_text_ids_on_save():
    """Test that text_id is auto-populated when saving course-lists"""
    # Create a course website with sitemetadata
    course_website = WebsiteFactory.create(url_path="courses/test-course-2025")
    sitemetadata = WebsiteContentFactory.create(
        website=course_website,
        type=constants.CONTENT_TYPE_METADATA,
    )

    # Create an ocw-www website for the course-list
    ocw_www = WebsiteFactory.create(name="ocw-www")

    # Create a course-list WITHOUT text_id in the courses entries
    course_list = WebsiteContentFactory.create(
        website=ocw_www,
        type=constants.CONTENT_TYPE_COURSE_LIST,
        metadata={
            "courses": [
                {
                    "id": "courses/test-course-2025",
                    "title": "Test Course 2025",
                    # Note: no text_id here
                }
            ]
        },
    )

    # Refresh from database
    course_list.refresh_from_db()

    # Verify text_id was auto-populated by the signal
    assert len(course_list.metadata["courses"]) == 1
    assert course_list.metadata["courses"][0]["id"] == "courses/test-course-2025"
    assert course_list.metadata["courses"][0]["title"] == "Test Course 2025"
    assert course_list.metadata["courses"][0]["text_id"] == sitemetadata.text_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("setup_course", "existing_text_id", "expected_behavior"),
    [
        (
            True,
            "00000000-0000-0000-0000-000000000000",
            "preserves_existing",
        ),  # Existing text_id should be preserved
        (
            False,
            None,
            "missing_website",
        ),  # Missing website should not add text_id
    ],
)
def test_populate_course_list_text_ids_edge_cases(
    setup_course, existing_text_id, expected_behavior
):
    """Test edge cases: existing text_id preservation and missing website handling"""
    ocw_www = WebsiteFactory.create(name="ocw-www")
    sitemetadata = None

    # Setup course website if needed
    if setup_course:
        course_website = WebsiteFactory.create(url_path="courses/test-course-2025")
        sitemetadata = WebsiteContentFactory.create(
            website=course_website,
            type=constants.CONTENT_TYPE_METADATA,
        )

    # Prepare metadata
    course_metadata = {
        "id": "courses/test-course-2025"
        if setup_course
        else "courses/non-existent-course",
        "title": "Test Course 2025" if setup_course else "Non-Existent Course",
    }
    if existing_text_id:
        course_metadata["text_id"] = existing_text_id

    # Create course-list
    course_list = WebsiteContentFactory.create(
        website=ocw_www,
        type=constants.CONTENT_TYPE_COURSE_LIST,
        metadata={"courses": [course_metadata]},
    )

    # Refresh from database
    course_list.refresh_from_db()

    # Verify behavior based on test case
    if expected_behavior == "preserves_existing":
        # Existing text_id should be preserved
        assert course_list.metadata["courses"][0]["text_id"] == existing_text_id
        assert course_list.metadata["courses"][0]["text_id"] != sitemetadata.text_id
    elif expected_behavior == "missing_website":
        # Missing website should not add text_id
        assert "text_id" not in course_list.metadata["courses"][0]


@pytest.mark.django_db
def test_populate_course_list_text_ids_handles_multiple_courses():
    """Test that signal populates text_id for multiple courses"""
    # Create two course websites with sitemetadata
    course1_website = WebsiteFactory.create(url_path="courses/course-1")
    course1_sitemetadata = WebsiteContentFactory.create(
        website=course1_website,
        type=constants.CONTENT_TYPE_METADATA,
    )

    course2_website = WebsiteFactory.create(url_path="courses/course-2")
    course2_sitemetadata = WebsiteContentFactory.create(
        website=course2_website,
        type=constants.CONTENT_TYPE_METADATA,
    )

    # Create an ocw-www website for the course-list
    ocw_www = WebsiteFactory.create(name="ocw-www")

    # Create a course-list with multiple courses
    course_list = WebsiteContentFactory.create(
        website=ocw_www,
        type=constants.CONTENT_TYPE_COURSE_LIST,
        metadata={
            "courses": [
                {
                    "id": "courses/course-1",
                    "title": "Course 1",
                },
                {
                    "id": "courses/course-2",
                    "title": "Course 2",
                },
            ]
        },
    )

    # Refresh from database
    course_list.refresh_from_db()

    # Verify text_id was populated for both courses
    assert len(course_list.metadata["courses"]) == 2
    assert course_list.metadata["courses"][0]["text_id"] == course1_sitemetadata.text_id
    assert course_list.metadata["courses"][1]["text_id"] == course2_sitemetadata.text_id
