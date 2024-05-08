"""Tests for link_resolveuid.py"""
import factory
import pytest

from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.rules.link_resolveuid import (
    LinkResolveuidRule,
)

EXAMPLE_RESOLVEUID = "89ce47d27edcdd9b8a8cbe641a59b520"
EXAMPLE_RESOLVEUID_FORMATTED = "89ce47d2-7edc-dd9b-8a8c-be641a59b520"


def get_cleaner():
    """Get cleaner for this test module."""
    rule = LinkResolveuidRule()
    return Cleaner(rule)


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("content", "expected_content"),
    [
        (
            Rf"""
            [![fix this](/courses/course-id/resources/image.png)](./resolveuid/{EXAMPLE_RESOLVEUID})
            ![fix this](./resolveuid/{EXAMPLE_RESOLVEUID})
            [fix this](./resolveuid/{EXAMPLE_RESOLVEUID})
            [not this](courses/course-id/resources/{EXAMPLE_RESOLVEUID})
            """,
            Rf"""
            {{{{% resource_link "{EXAMPLE_RESOLVEUID_FORMATTED}" "![fix this](/courses/course-id/resources/image.png)" %}}}}
            {{{{< resource uuid="{EXAMPLE_RESOLVEUID_FORMATTED}" >}}}}
            {{{{% resource_link "{EXAMPLE_RESOLVEUID_FORMATTED}" "fix this" %}}}}
            [not this](courses/course-id/resources/{EXAMPLE_RESOLVEUID})
            """,
        ),
    ],
)
def test_resolveuid_content_text_id(content, expected_content):
    """
    Test resolveuid links are replaced with content that has
    matching text_id.
    """
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(website=website, text_id=EXAMPLE_RESOLVEUID_FORMATTED)
    target_content = WebsiteContentFactory.create(
        markdown=content,
        website=website,
    )
    cleaner = get_cleaner()
    cleaner.update_website_content(target_content)
    assert target_content.markdown == expected_content


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("content", "expected_content"),
    [
        (
            Rf"""
            [![fix this](/courses/course-id/resources/image.png)](./resolveuid/{EXAMPLE_RESOLVEUID})
            ![fix this](./resolveuid/{EXAMPLE_RESOLVEUID})
            [fix this](./resolveuid/{EXAMPLE_RESOLVEUID})
            """,
            R"""
            [![fix this](/courses/course-id/resources/image.png)](/courses/site-path)
            [fix this](/courses/site-path)
            [fix this](/courses/site-path)
            """,
        ),
    ],
)
def test_resolveuid_website_legacy_uid(content, expected_content):
    """
    Test resolveuid links are replaced with website
    that has a matching legacy uid.
    """
    WebsiteFactory.create(
        url_path="courses/site-path",
        metadata={
            "legacy_uid": EXAMPLE_RESOLVEUID_FORMATTED,
        },
    )
    website = WebsiteFactory.create()

    target_content = WebsiteContentFactory.create(
        markdown=content,
        website=website,
    )

    cleaner = get_cleaner()
    cleaner.update_website_content(target_content)
    assert target_content.markdown == expected_content


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("content", "expected_content"),
    [
        (
            Rf"""
            ![Unique Title 1](./resolveuid/{EXAMPLE_RESOLVEUID})
            [Unique Title 2](./resolveuid/{EXAMPLE_RESOLVEUID})
            [Duplicate Title](./resolveuid/{EXAMPLE_RESOLVEUID})
            [Duplicate Title](./resolveuid/{EXAMPLE_RESOLVEUID})
            [Missing](./resolveuid/{EXAMPLE_RESOLVEUID})
            """,
            Rf"""
            {{{{< resource uuid="89ce47d2-7edc-dd9b-8a8c-be641a59b521" >}}}}
            {{{{% resource_link "89ce47d2-7edc-dd9b-8a8c-be641a59b522" "Unique Title 2" %}}}}
            [Duplicate Title](./resolveuid/{EXAMPLE_RESOLVEUID})
            [Duplicate Title](./resolveuid/{EXAMPLE_RESOLVEUID})
            [Missing](./resolveuid/{EXAMPLE_RESOLVEUID})
            """,
        ),
    ],
)
def test_resolveuid_matching_title(content, expected_content):
    """
    Test resolveuid links are replaced with content that
    has a matching title.
    """
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        4,
        website=website,
        title=factory.Iterator(
            ["Unique Title 1", "Unique Title 2", "Duplicate Title", "Duplicate Title"]
        ),
        text_id=factory.Iterator(
            [
                "89ce47d2-7edc-dd9b-8a8c-be641a59b521",
                "89ce47d2-7edc-dd9b-8a8c-be641a59b522",
                "89ce47d2-7edc-dd9b-8a8c-be641a59b523",
                "89ce47d2-7edc-dd9b-8a8c-be641a59b524",
            ]
        ),
    )
    target_content = WebsiteContentFactory.create(
        markdown=content,
        website=website,
    )
    cleaner = get_cleaner()
    cleaner.update_website_content(target_content)
    assert target_content.markdown == expected_content
