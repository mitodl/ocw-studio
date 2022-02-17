"""Tests for convert_baseurl_links_to_resource_links.py"""
import pytest

from websites.factories import WebsiteContentFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.legacy_shortcodes_data_fix import (
    LegacyShortcodeFixOne,
    LegacyShortcodeFixTwo,
)


@pytest.mark.parametrize(
    ["markdown", "expected_markdown"],
    [
        (
            # images inside links
            R"cats \[!\[ Image description.\]({{\< resource\_file uuid1 >}})\]({{\< meow",
            R"cats [![ Image description.]({{\< resource_file uuid1 >}})]({{\< meow",
        ),
        (
            # two on same line
            R"\[post-class assignments\]({{\< some_shortcode >}}) woof \[post-class assignments\]({{\< woof",
            R"[post-class assignments]({{\< some_shortcode >}}) woof [post-class assignments]({{\< woof",
        ),
    ],
)
def test_baseurl_replacer_specific_title_replacements(markdown, expected_markdown):
    """Test specific replacements"""
    website_uuid = "website-uuid"
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )

    cleaner = Cleaner(LegacyShortcodeFixOne())
    cleaner.update_website_content_markdown(target_content)
    assert target_content.markdown == expected_markdown


@pytest.mark.parametrize(
    ["markdown", "expected_markdown"],
    [
        (
            R"cats [![ Image description.]({{\< resource_file uuid1 >}})]({{\< meow >}} cool",
            R"cats [![ Image description.]({{< resource_file uuid1 >}})]({{< meow >}} cool",
        ),
        (
            # without space on closing shortcode
            R'{{\< div-with-class "reveal1">}}',
            R'{{< div-with-class "reveal1">}}',
        ),
        (
            # with space
            R'{{\< div-with-class "reveal1" >}}',
            R'{{< div-with-class "reveal1" >}}',
        ),
    ],
)
def test_baseurl_replacer_specific_title_replacements(markdown, expected_markdown):
    """Test specific replacements"""
    website_uuid = "website-uuid"
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )

    cleaner = Cleaner(LegacyShortcodeFixTwo())
    cleaner.update_website_content_markdown(target_content)

    assert target_content.markdown == expected_markdown
