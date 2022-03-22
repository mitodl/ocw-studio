import pytest

from websites.management.commands.markdown_cleaning.parsing_utils import (
    unescape_quoted_string
)
from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParser,
    ShortcodeTag,
)


@pytest.mark.parametrize(
    ["text", "expected"],
    [
        (
            # Quote all the things
            R"The quick {{< blargle doesnt_need_quotes >}} brown fox",
            R'The quick {{< blargle "doesnt_need_quotes" >}} brown fox',
        ),
        (
            # Pyparsing hates whitespace.
            R"The quick {{< sup    2 >}} brown fox",
            R'The quick {{< sup "2" >}} brown fox',
        ),
        (
            # Example: Convert shortcode delimiter
            R'Take {{< resource_link uuid "that {{< sup 123 >}}" >}}, regex.',
            R'Take {{% resource_link "uuid" "that {{< sup 123 >}}" %}}, regex.',
        ),
        (
            # Example: Convert shortcode delimiter
            # Not a resource_link, so left alone.
            R'Quotes: {{< some_shortcode unnecessary_quotes "spaces are fun" "spaces \"and\" quotes" >}}, regex.',
            R'Quotes: {{< some_shortcode "unnecessary_quotes" "spaces are fun" "spaces \"and\" quotes" >}}, regex.',
        ),
    ],
)
def test_shortcode_grammar_transform_string(text, expected):
    """Example transform_string usage.

    This example will:
        - standardize whitespace in all shortcodes
        - convert resource_link shortcodes to percent delimiters
    """
    parser = ShortcodeParser()

    def parse_action(_s, _l, toks):
        shortcode = toks.shortcode
        if shortcode.name == "resource_link":
            replacement = ShortcodeTag(
                name=shortcode.name, args=shortcode.args, percent_delimiters=True
            )
            return replacement.to_hugo()
        return shortcode.to_hugo()

    parser.set_parse_action(parse_action)
    out = parser.transform_string(text)
    assert out == expected


def test_original_text_records_during_transform_text():
    """Check that parse actions record the original text of individual matches."""

    text = R"""
    Some {{< cool_shortcode abc   "xy z" >}}. And {{< cat another   one >}}

    And {{% dog one   "more \"with quotes\" !" %}}
    """
    expected = [
        R'{{< cool_shortcode abc   "xy z" >}}',
        R"{{< cat another   one >}}",
        R'{{% dog one   "more \"with quotes\" !" %}}',
    ]
    original_texts = []

    def parse_action(s, l, toks):
        original_texts.append(toks.original_text)
        return toks.original_text

    parser = ShortcodeParser()
    parser.set_parse_action(parse_action)

    assert parser.transform_string(text) == text
    assert original_texts == expected

@pytest.mark.parametrize(['escaped', 'unescaped'], [
    (
        R'''"cats \"and\" 'dogs' are cool."''',
        R'''cats "and" 'dogs' are cool.'''
    ),
    (
        R'''"backslashes \\\" are \\ ok"''',
        R'''backslashes \" are \ ok''',
    ),
    (
        R"""'cats \'and\' "dogs" are cool.'""",
        R"""cats 'and' "dogs" are cool."""
    ),
    (
        R"""'backslashes \\\' are \\ ok'""",
        R"""backslashes \' are \ ok""",
    )
])
def test_unescape_quoted_string(escaped, unescaped):
    assert unescape_quoted_string(escaped) == unescaped

@pytest.mark.parametrize('bad_text', [
    """cat""",
    """'cat""",
    """cat'""",
    '''cat''',
    '''"cat''',
    '''cat"''',
    '"missing "escapes" so sad "',
    "'missing 'escapes' so sad '",
])
def test_unescape_quoted_string(bad_text):
    with pytest.raises(ValueError):
        assert unescape_quoted_string(bad_text)