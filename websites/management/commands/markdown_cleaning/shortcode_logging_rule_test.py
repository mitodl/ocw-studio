"""Tests for convert_baseurl_links_to_resource_links.py"""
from content_sync.factories import ContentSyncStateFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.shortcode_logging_rule_test import (
    ShortcodeLoggingRule,
)


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""
    rule = ShortcodeLoggingRule()
    return WebsiteContentMarkdownCleaner(rule)


def test_shortcode_standardizer():
    """Check that it replaces resource_file links as expected"""
    markdown = R"""
    Roar {{< cat uuid    "some \"text\" cool">}}

    {{< dog a     b >}}

    Hello world {{< wolf "a     b" >}}
    """
    expected_markdown = R"""
    Roar {{< cat uuid "some \"text\" cool" >}}

    {{< dog a b >}}

    Hello world {{< wolf "a     b" >}}
    """
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )
    ContentSyncStateFactory.build(content=target_content)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected_markdown
