"""Tests for course_absolute_link.py"""
import pytest

from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.rules.course_absolute_link import (
    CourseAbsoluteLinkRule,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    patch_website_all,
    patch_website_contents_all,
)


def get_cleaner(website_contents, websites):
    """Get cleaner for this test module."""
    with patch_website_contents_all(website_contents), patch_website_all(websites):
        rule = CourseAbsoluteLinkRule()
        return Cleaner(rule)


@pytest.mark.parametrize(
    ("content", "expected_content"),
    [
        (
            R"""
            [![fix this](courses/course-id/resources/image.png)](courses/course-id)
            [fix this](courses/course-id)
            [not this](courses/course-id-404)
            [not this](/courses/course-id)
            [not this](courses/course-id/bio/bio1)
            [not this](/courses/course-id/bio/bio1)
            [not this]({{< baseurl >}}/bio/bio1)
            """,
            R"""
            [![fix this](courses/course-id/resources/image.png)](/courses/course-id)
            [fix this](/courses/course-id)
            [not this](courses/course-id-404)
            [not this](/courses/course-id)
            [not this](courses/course-id/bio/bio1)
            [not this](/courses/course-id/bio/bio1)
            [not this]({{< baseurl >}}/bio/bio1)
            """,
        ),
    ],
)
def test_course_links_are_correctly_absolutized(content, expected_content):
    """Test course (home) relative links are absolutized."""
    linked_website = WebsiteFactory.build(url_path="courses/course-id")
    website = WebsiteFactory.build(starter=WebsiteStarterFactory.build())
    linked_content = WebsiteContentFactory.build(
        website=website, type="bio", dirpath="content/bio", filename="bio1"
    )
    target_content = WebsiteContentFactory.build(
        markdown=content,
        website=website,
        metadata={
            "description": content,
            "related_resources_text": content,
            "optional_text": content,
            "course_description": content,
            "image_metadata": {
                "caption": content,
                "credit": content,
            },
        },
    )

    cleaner = get_cleaner([linked_content, target_content], [linked_website, website])
    cleaner.update_website_content(target_content)
    assert target_content.markdown == expected_content

    for field in [
        "description",
        "related_resources_text",
        "optional_text",
        "course_description",
    ]:
        assert target_content.metadata[field] == expected_content

    for field in ["credit", "caption"]:
        assert target_content.metadata["image_metadata"][field] == expected_content
