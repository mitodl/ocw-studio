"""Tests for convert_baseurl_links_to_resource_links.py"""
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.shortcode_logging_rule import (
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
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == markdown
