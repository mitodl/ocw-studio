"""Tests for broken_link_fix.py"""

import factory
import pytest

from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.rules.broken_link_fix import (
    BrokenMarkdownLinkFixRule,
    BrokenMetadataLinkFixRule,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    patch_website_all,
    patch_website_contents_all,
    patch_website_starter_all,
)

EXAMPLE_UUIDS = [
    "89ce47d2-7edc-dd9b-8a8c-be641a59b521",
    "89ce47d2-7edc-dd9b-8a8c-be641a59b522",
    "89ce47d2-7edc-dd9b-8a8c-be641a59b523",
    "89ce47d2-7edc-dd9b-8a8c-be641a59b524",
]


def get_cleaner(rule_type, website_contents, websites, starters):
    """Get cleaner for this test module."""
    with (
        patch_website_contents_all(website_contents),
        patch_website_all(websites),
        patch_website_starter_all(starters),
    ):
        if rule_type == "markdown":
            rule = BrokenMarkdownLinkFixRule()
        else:
            rule = BrokenMetadataLinkFixRule()

        return Cleaner(rule)


@pytest.mark.parametrize(
    ("field_type", "content", "expected_content"),
    [
        (
            "markdown",
            R"""
            ![fix this](/courses/course-id/bio/bio1/_index)
            [fix this](/courses/course-id/bio/bio1/_index)
            [fix this](courses/course-id/bio/bio1/_index#123)
            [fix this](/bio/bio1/_index)
            [fix this]({{< baseurl >}}/bio/bio1/_index)
            ![fix this](/courses/course-id/pages/section/bio/bio2)
            [fix this](/courses/course-id/pages/section/bio/bio2)
            [fix this](courses/course-id/pages/section/bio/bio2#123)
            [fix this](/pages/section/bio/bio2)
            [fix this](bio/bio2)
            [fix this]({{< baseurl >}}/pages/section/bio/bio2)
            [not this](bio/bio1/_index)
            [not this](/bio/bio1)
            [not this](/courses/course-id/bio/bio1)
            [not this](/pages/section/bio/duplicate)
            [not this](/courses/course-id-2/bio/bio1/_index)
            [not this](bio/bio3)
            """,
            Rf"""
            {{{{< resource uuid="{EXAMPLE_UUIDS[0]}" >}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[0]}" "fix this" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[0]}" "fix this" "#123" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[0]}" "fix this" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[0]}" "fix this" %}}}}
            {{{{< resource uuid="{EXAMPLE_UUIDS[1]}" >}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[1]}" "fix this" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[1]}" "fix this" "#123" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[1]}" "fix this" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[1]}" "fix this" %}}}}
            {{{{% resource_link "{EXAMPLE_UUIDS[1]}" "fix this" %}}}}
            [not this](bio/bio1/_index)
            [not this](/bio/bio1)
            [not this](/courses/course-id/bio/bio1)
            [not this](/pages/section/bio/duplicate)
            [not this](/courses/course-id-2/bio/bio1/_index)
            [not this](bio/bio3)
            """,
        ),
        (
            "metadata",
            R"""
            ![fix this](/courses/course-id/bio/bio1/_index)
            [fix this](/courses/course-id/bio/bio1/_index)
            [fix this](courses/course-id/bio/bio1/_index#123)
            [fix this](/bio/bio1/_index)
            [fix this]({{< baseurl >}}/bio/bio1/_index)
            ![fix this](/courses/course-id/pages/section/bio/bio2)
            [fix this](/courses/course-id/pages/section/bio/bio2)
            [fix this](courses/course-id/pages/section/bio/bio2#123)
            [fix this](/pages/section/bio/bio2)
            [fix this](bio/bio2)
            [fix this]({{< baseurl >}}/pages/section/bio/bio2)
            [not this](bio/bio1/_index)
            [not this](/bio/bio1)
            [not this](/courses/course-id/bio/bio1)
            [not this](/pages/section/bio/duplicate)
            [not this](/courses/course-id-2/bio/bio1/_index)
            [not this](bio/bio3)
            """,
            R"""
            ![fix this](/courses/course-id/bio/bio1)
            [fix this](/courses/course-id/bio/bio1)
            [fix this](/courses/course-id/bio/bio1#123)
            [fix this](/courses/course-id/bio/bio1)
            [fix this](/courses/course-id/bio/bio1)
            ![fix this](/courses/course-id/bio/bio2)
            [fix this](/courses/course-id/bio/bio2)
            [fix this](/courses/course-id/bio/bio2#123)
            [fix this](/courses/course-id/bio/bio2)
            [fix this](/courses/course-id/bio/bio2)
            [fix this](/courses/course-id/bio/bio2)
            [not this](bio/bio1/_index)
            [not this](/bio/bio1)
            [not this](/courses/course-id/bio/bio1)
            [not this](/pages/section/bio/duplicate)
            [not this](/courses/course-id-2/bio/bio1/_index)
            [not this](bio/bio3)
            """,
        ),
    ],
)
def test_broken_links(field_type, content, expected_content):
    """Test broken links are fixed."""
    starter = WebsiteStarterFactory.build()
    related_website = WebsiteFactory.build(
        url_path="courses/course-id-2", starter=starter, starter_id=starter.id
    )
    website = WebsiteFactory.build(
        url_path="courses/course-id", starter=starter, starter_id=starter.id
    )

    linked_contents = WebsiteContentFactory.build_batch(
        4,
        website=website,
        type="bio",
        dirpath=factory.Iterator(
            ["content/bio/bio1", "content/bio", "content/bio", "content/blog"]
        ),
        filename=factory.Iterator(["_index", "bio2", "duplicate", "duplicate"]),
        text_id=factory.Iterator(EXAMPLE_UUIDS),
    )

    linked_contents.append(
        WebsiteContentFactory.build(
            website=related_website, type="bio", dirpath="content/bio", filename="bio3"
        )
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

    cleaner = get_cleaner(
        field_type,
        [*linked_contents, target_content],
        [related_website, website],
        [starter],
    )
    cleaner.update_website_content(target_content)

    if field_type == "markdown":
        assert target_content.markdown == expected_content
    else:
        for field in [
            "description",
            "related_resources_text",
            "optional_text",
            "course_description",
        ]:
            assert target_content.metadata[field] == expected_content

        for field in ["credit", "caption"]:
            assert target_content.metadata["image_metadata"][field] == expected_content
