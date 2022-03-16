import pytest

from websites.management.commands.markdown_cleaning.parsing_utils import (
    Shortcode,
    ShortcodeParser,
)

@pytest.mark.parametrize(['percent_delimiters'], [(False,), (True,)])
def test_shortcode(percent_delimiters):
    shortocde = Shortcode(
        name='my_shortcode',
        args=['first', 'second   2'],
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
    parsed_shortcode = parsed[0]

    assert len(parsed) == 1
    assert parsed_shortcode.shortcode == Shortcode('some_name', args=[
        'first_arg',
        '2',
        '3rd "quoted"   arg',
        'fourth'
    ])
    assert parsed_shortcode.original_text == text


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
    text_quoted = R'{{< fake_shortcode uuid "{{< sup 4 >}}" >}}'
    quoted = parser.parse_string(R'{{< fake_shortcode uuid "{{< sup 4 >}}" >}}')
    assert len(quoted) == 1

    assert quoted[0].shortcode == Shortcode('fake_shortcode', args=[
        'uuid',
        R'{{< sup 4 >}}'
    ])
    assert quoted[0].original_text == text_quoted

    # Here "sup" and "4" are captured as separate arguments.
    text_not_nested = R"{{< fake_shortcode uuid sup 4 >}}"
    not_nested = parser.parse_string(text_not_nested)
    assert len(not_nested) == 1
    assert not_nested[0].shortcode == Shortcode(name='fake_shortcode', args = ['uuid', 'sup', '4'])
    assert not_nested[0].original_text == text_not_nested
    
    # "real" nesting raises an error:

    with pytest.raises(ValueError, match='nesting'):
        text_nested = R'{{< fake_shortcode uuid {{< sup 4 >}} "Cats and dogs" >}}'
        parser.parse_string(text_nested)

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
        ),
        (
            # Example: Convert shortcode delimiter
            # Not a resource_link, so left alone.
           R'Quotes: {{< some_shortcode no_quotes "spaces are fun" "spaces \"and\" quotes" >}}, regex.',
           R'Quotes: {{< some_shortcode no_quotes "spaces are fun" "spaces \"and\" quotes" >}}, regex.',
        )
    ]
)
def test_shortcode_grammar_transform_string(text, expected):
    parser = ShortcodeParser()
    def parse_action(_s, _l, toks):
        shortcode = toks[0].shortcode
        if shortcode.name == 'resource_link':
            replacement = Shortcode(name=shortcode.name, args=shortcode.args, percent_delimiters=True)
            return replacement.to_hugo()
        return shortcode.to_hugo()
    parser.add_parse_action(parse_action)
    out = parser.transform_string(text)
    assert out == expected