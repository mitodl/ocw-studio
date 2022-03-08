"""Tests for convert_baseurl_links_to_resource_links.py"""
from content_sync.factories import ContentSyncStateFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
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
    website = WebsiteFactory.build()
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
    target_content = WebsiteContentFactory.build(markdown=markdown, website=website)
    ContentSyncStateFactory.build(content=target_content)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected_markdown
    assert (
        target_content.content_sync_state.current_checksum
        == target_content.calculate_checksum()
    )
