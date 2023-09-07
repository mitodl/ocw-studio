import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.rules.resource_link_nextprev import (
    ResourceLinkNextPrevRule,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    allow_invalid_uuids,
)


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""  # noqa: D401
    rule = ResourceLinkNextPrevRule()
    return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(
    ("markdown", "expected_markdown"),
    [
        (
            R'cats {{% resource_link "uuid" "\<\<Previous!" %}} replace + space',
            R'cats {{% resource_link "uuid" "« Previous!" %}} replace + space',
        ),
        (
            R'cats {{% resource_link "uuid" "\<\< Previous!" %}} replace',
            R'cats {{% resource_link "uuid" "« Previous!" %}} replace',
        ),
        (
            R'cats {{% resource_link "uuid" "\< Previous!" %}} replace',
            R'cats {{% resource_link "uuid" "« Previous!" %}} replace',
        ),
        (
            R'cats {{% resource_link "uuid" "Previous!" %}} stay same',
            R'cats {{% resource_link "uuid" "Previous!" %}} stay same',
        ),
        (
            R'cats {{% resource_link "uuid" "\>\> Next!" %}} replace',
            R'cats {{% resource_link "uuid" "» Next!" %}} replace',
        ),
        (
            R'cats {{% resource_link "uuid" "\> Next!" %}} replace',
            R'cats {{% resource_link "uuid" "» Next!" %}} replace',
        ),
        (
            R'cats {{% resource_link "uuid" "Next!" %}} stay same',
            R'cats {{% resource_link "uuid" "Next!" %}} stay same',
        ),
    ],
)
@allow_invalid_uuids()
def test_prevnext_replacement(markdown, expected_markdown):
    """Test subscript/superscript replacements"""
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected_markdown
