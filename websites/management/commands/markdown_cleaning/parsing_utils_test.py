from unittest.mock import Mock

import pytest

from websites.management.commands.markdown_cleaning.parsing_utils import (
    Shortcode,
    ShortcodeParser,
)

@pytest.mark.parametrize(['percent_delimiters'], [(False,), (True,)])
def test_shortcode(percent_delimiters):
    shortocde = Shortcode(
        name='my_shortcode',
        args=['first', '"second   2"'],
        percent_delimiters=percent_delimiters
    )

    if percent_delimiters:
        assert shortocde.to_hugo() == R'{{% my_shortcode first "second   2" %}}'
    else:
        assert shortocde.to_hugo() == R'{{< my_shortcode first "second   2" >}}'


def test_shortcode_grammar_respects_spaces_in_quoted_arguments():
    text = R'{{< some_name first_arg 2 "3rd \"quoted\"   arg" fourth >}}'
    parser = ShortcodeParser()
    parsed = parser.parse_string(text)
    assert parsed[0] == Shortcode('some_name', args=[
        'first_arg',
        '2',
        R'"3rd \"quoted\"   arg"',
        'fourth'
    ])


def test_shortcode_grammar_with_nested_shortcodes():
    """Check parses shortcodes with arguments containing shortcode delimiters.

    For example:
        '{{< fake_shortcode uuid "E=mc{{< sup 2 >}}" >}}'

    This won't show up properly in Hugo, but (the superscript shortcode is
    rendered more-or-less raw) but we still want find-and-replace to capture
    the correct end of the fake_shortcode. (This situationcaused trouble for
    regex-based approach when we changed resource_link delimiters to %.)
    """

    # Here pyparsing captures "{{< sup 4 >}}" as a single item since it is quoted.
    parser = ShortcodeParser()
    quoted = parser.parse_string(R'{{< fake_shortcode uuid "{{< sup 4 >}}" >}}')

    print(quoted)
    assert quoted[0] == Shortcode('fake_shortcode', args=[
        'uuid',
        R'"{{< sup 4 >}}"'
    ])

    # Here "sup" and "4" are captured as separate arguments.
    not_nested = parser.parse_string(R"{{< fake_shortcode uuid sup 4 >}}")
    assert not_nested[0] == Shortcode(name='fake_shortcode', args = ['uuid', 'sup', '4'])

    # Here "sup" and "4" are captured as separate arguments of a nested expression
    mock_parse_action = Mock(wraps=lambda _s, _l, toks: toks)
    parser.add_parse_action(mock_parse_action)
    unquoted = parser.parse_string(R'{{< fake_shortcode uuid {{< sup 4 >}} "Cats and dogs" >}}')
    assert unquoted[0] == Shortcode('fake_shortcode', args=[
        'uuid',
        Shortcode('sup', ['4']),
        '"Cats and dogs"'
    ])
    assert mock_parse_action.call_count == 2

@pytest.mark.parametrize(
    ['text', 'expected'],
    [
        (
            # Pyparsing hates whitespace
           R"The quick {{< sup    2 >}} brown fox",
           R"The quick {{< sup 2 >}} brown fox"
        ),
        (
            # Example: Convert shortcode delimiter
           R'Take {{< resource_link uuid "that {{< sup 123 >}}" >}}, regex.',
           R'Take {{% resource_link uuid "that {{< sup 123 >}}" %}}, regex.',
        )
    ]
)
def test_shortcode_grammar_transform_string(text, expected):
    text = R'The quick {{< sup 2 >}} brown fox'
    parser = ShortcodeParser()
    def parse_action(_s, _l, toks):
        shortcode = toks[0]
        if shortcode.name == 'resource_link':
            replacement = Shortcode(name=shortcode.name, args=shortcode.args, percent_delimiters=True)
            return replacement.to_hugo()
        return shortcode.to_hugo()
    parser.add_parse_action(parse_action)
    out = parser.transform_string(text)
    assert out == expected