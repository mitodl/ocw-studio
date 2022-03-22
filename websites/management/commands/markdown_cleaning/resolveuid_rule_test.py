import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.resolveuid_rule import (
    ResolveUIDRule,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    patch_website_contents_all,
)


def get_markdown_cleaner(website_contents):
    """Convenience to get rule-specific markdown cleaner"""
    with patch_website_contents_all(website_contents):
        rule = ResolveUIDRule()
        return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(
    ["markdown", "expected"],
    [
        (
            "Here is a [resolveuid link](./resolveuid/5cf754b2b97b4ac18dabdeed1201de94) cool",
            R'Here is a {{% resource_link "5cf754b2-b97b-4ac1-8dab-deed1201de94" "resolveuid link" %}} cool',
        ),
        (
            "Here is an image ![should disappear](./resolveuid/5cf754b2b97b4ac18dabdeed1201de94) cool",
            R'Here is an image {{< resource "5cf754b2-b97b-4ac1-8dab-deed1201de94" >}} cool',
        ),
    ],
)
def test_resolveuid_conversion_within_same_site(markdown, expected):
    """Check shortcodes are used within same site."""
    website = WebsiteFactory.build()
    target_content = WebsiteContentFactory.build(markdown=markdown, website=website)
    linked_content = WebsiteContentFactory.build(
        text_id="5cf754b2-b97b-4ac1-8dab-deed1201de94", website=website
    )

    cleaner = get_markdown_cleaner([target_content, linked_content])
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected


@pytest.mark.parametrize(
    ["markdown", "expected"],
    [
        (
            "Here is a [resolveuid link text](./resolveuid/5cf754b2b97b4ac18dabdeed1201de94) cool",
            R"Here is a [resolveuid link text](/courses/other-site-name/pages/path/to/thing) cool",
        ),
        (
            "Here is a ![resolveuid link text](./resolveuid/5cf754b2b97b4ac18dabdeed1201de94) cool",
            R"Here is a ![resolveuid link text](/courses/other-site-name/pages/path/to/thing) cool",
        ),
    ],
)
def test_resolveuid_conversion_cross_site(markdown, expected):
    """Check shortcodes are used within same site."""
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )
    linked_content = WebsiteContentFactory.build(
        text_id="5cf754b2-b97b-4ac1-8dab-deed1201de94",
        dirpath="content/pages/path/to",
        filename="thing",
        website=WebsiteFactory.build(name="other-site-name"),
    )

    cleaner = get_markdown_cleaner([target_content, linked_content])
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected


@pytest.mark.parametrize(
    ["markdown", "expected"],
    [
        (
            "Should leave alone if uuid not exist in db [resolveuid link text](./resolveuid/5cf754b2b97b4ac18dabdeed1201de94) cool",
            "Should leave alone if uuid not exist in db [resolveuid link text](./resolveuid/5cf754b2b97b4ac18dabdeed1201de94) cool",
        ),
        (
            "And if uuid is not valid ![resolveuid link text](./resolveuid/woofwoof) cool",
            "And if uuid is not valid ![resolveuid link text](./resolveuid/woofwoof) cool",
        ),
    ],
)
def test_resolveuid_leaves_stuff_alone_if_it_should(markdown, expected):
    """Check shortcodes are used within same site."""
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )

    cleaner = get_markdown_cleaner([target_content])
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected
