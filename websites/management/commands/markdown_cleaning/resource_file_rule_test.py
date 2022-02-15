"""Tests for convert_baseurl_links_to_resource_links.py"""

from websites.factories import WebsiteContentFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.resource_file_rule import (
    ResourceFileReplacementRule,
)


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""
    rule = ResourceFileReplacementRule()
    return WebsiteContentMarkdownCleaner(rule)


def test_resource_file_replacer():
    """Check that it replaces resource_file links as expected"""
    website_uuid = "website-uuid"
    markdown = R"""
    Look an image ![Some alt text here]({{< resource_file uuid-1 >}}) cool.
    
    And here is another one: ![more alt text]({{< resource_file uuid-2 >}})

    nice.
    """
    expected_markdown = R"""
    Look an image {{< resource uuid-1 >}} cool.
    
    And here is another one: {{< resource uuid-2 >}}

    nice.
    """
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content_markdown(target_content)

    assert target_content.markdown == expected_markdown
