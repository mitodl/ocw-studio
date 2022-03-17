import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.remove_extra_resource_args import (
    RemoveExtraResourceArgs,
)


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""
    rule = RemoveExtraResourceArgs()
    return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(['text', 'expected'], [
    (
        # If single arg, do not touch at all.
        R'Hello {{< resource uuid >}}',
        R'Hello {{< resource uuid >}}'
    ),
    (   # If not resource, don't touch at all.
        R'Hello {{< cat uuid "some other" args >}}',
        R'Hello {{< cat uuid "some other" args >}}'
    ),
    (
        R'Hello {{< resource uuid "extra" args >}}',
        R'Hello {{< resource "uuid" >}}'
    ),
])
def test_shortcode_standardizer(text, expected):
    """Check that it removes extra args from resource shortcodes"""
    target_content = WebsiteContentFactory.build(
        markdown=text, website=WebsiteFactory.build()
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected
