import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.subsup_fixes import SubSupFixes


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""
    rule = SubSupFixes()
    return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(
    ["markdown", "expected_markdown"],
    [
        (
            R'The quick {{< sub "-cat" >}} brown fox',
            R'The quick {{< sub "\-cat" >}} brown fox',
        ),
        (
            R'The quick {{< sub "+cat" >}} brown fox',
            R'The quick {{< sub "\+cat" >}} brown fox',
        ),
        (
            R'The quick {{< sub "**cat**" >}} brown fox',
            R'The quick {{< sub "**cat**" >}} brown fox',
        ),
        (
            R'The quick {{< sub "-2+2-1" >}} brown fox',
            R'The quick {{< sub "\-2+2-1" >}} brown fox',
        ),
        (
            R'The quick {{< sub "+2+2-1" >}} brown fox',
            R'The quick {{< sub "\+2+2-1" >}} brown fox',
        ),
        (
            R'The quick {{< sup "-cat" >}} brown fox',
            R'The quick {{< sup "\-cat" >}} brown fox',
        ),
        (
            R'The quick {{< sup "+cat" >}} brown fox',
            R'The quick {{< sup "\+cat" >}} brown fox',
        ),
        (
            R'The quick {{< sup "**cat**" >}} brown fox',
            R'The quick {{< sup "**cat**" >}} brown fox',
        ),
        (
            R'The quick {{< sup "-2+2-1" >}} brown fox',
            R'The quick {{< sup "\-2+2-1" >}} brown fox',
        ),
        (
            R'The quick {{< sup "+2+2-1" >}} brown fox',
            R'The quick {{< sup "\+2+2-1" >}} brown fox',
        ),
    ],
)
def test_shortcode_standardizer(markdown, expected_markdown):
    """Test subscript/superscript replacements"""
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website=WebsiteFactory.build()
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(target_content)

    assert target_content.markdown == expected_markdown
