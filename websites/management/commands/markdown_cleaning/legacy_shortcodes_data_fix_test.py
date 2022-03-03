"""Tests for convert_baseurl_links_to_resource_links.py"""
import pytest

from content_sync.factories import ContentSyncStateFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
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
def test_legacy_shortcode_fix_one(markdown, expected_markdown):
    """Test specific replacements"""
    website = WebsiteFactory.build()
    target_content = WebsiteContentFactory.build(markdown=markdown, website=website)
    target_sync_state = ContentSyncStateFactory.build(content=target_content)

    cleaner = Cleaner(LegacyShortcodeFixOne())
    cleaner.update_website_content_markdown(target_content)
    assert target_content.markdown == expected_markdown
    assert target_sync_state.current_checksum == target_content.calculate_checksum()


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
def test_legacy_shortcode_fix_two(markdown, expected_markdown):
    """Test specific replacements"""
    website = WebsiteFactory.build()
    target_content = WebsiteContentFactory.build(markdown=markdown, website=website)
    ContentSyncStateFactory.build(content=target_content)

    cleaner = Cleaner(LegacyShortcodeFixTwo())
    cleaner.update_website_content_markdown(target_content)

    assert target_content.markdown == expected_markdown
    assert (
        target_content.content_sync_state.current_checksum
        == target_content.calculate_checksum()
    )
