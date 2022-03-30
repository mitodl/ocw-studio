"""Tests for convert_baseurl_links_to_resource_links.py"""
import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.link_unescape import LinkUnescape


@pytest.mark.parametrize(
    ["markdown", "expected_markdown"],
    [
        (
            # images inside links
            R"cats \[!\[ Image description.\]({{< resource\_file uuid1 >}})\]({{< meow",
            R"cats [![ Image description.]({{< resource_file uuid1 >}})]({{< meow",
        ),
        (
            # two on same line
            R"\[post-class assignments\]({{< some_shortcode >}}) woof \[post-class assignments\]({{< woof",
            R"[post-class assignments]({{< some_shortcode >}}) woof [post-class assignments]({{< woof",
        ),
    ],
)
def test_link_unescape(markdown, expected_markdown):
    """Test specific replacements"""
    website = WebsiteFactory.build()
    target_content = WebsiteContentFactory.build(markdown=markdown, website=website)

    cleaner = Cleaner(LinkUnescape())
    cleaner.update_website_content(target_content)
    assert target_content.markdown == expected_markdown
