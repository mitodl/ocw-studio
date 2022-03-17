"""Tests for convert_baseurl_links_to_resource_links.py"""
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.resource_link_delimiters import (
    ResourceLinkDelimitersReplacementRule,
)


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""
    rule = ResourceLinkDelimitersReplacementRule()
    return WebsiteContentMarkdownCleaner(rule)


def test_resource_file_replacer():
    """Check that it replaces resource_file links as expected"""
    markdown = R"""
    {{< resource_link uuid-1 "this is a link to a resource" >}}

    {{< resource_link uuid-2 "this is a link to another resource" >}}

    nice.
    """
    expected_markdown = R"""
    {{% resource_link uuid-1 "this is a link to a resource" %}}

    {{% resource_link uuid-2 "this is a link to another resource" %}}

    nice.
    """
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected_markdown
