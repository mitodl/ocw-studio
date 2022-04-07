import pytest

from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParam,
    ShortcodeParser,
    ShortcodeTag,
)


@pytest.mark.parametrize("closer", [True, False])
def test_shortcode_grammar_respects_spaces_in_quoted_positional_params(closer):
    symbol = "/" if closer else ""
    text = f'{{{{<{symbol} some_name first_arg 2 "3rd \\"quoted\\"   arg" fourth >}}}}'
    parser = ShortcodeParser()
    parsed = parser.parse_string(text)

    assert parsed.shortcode == ShortcodeTag(
        "some_name",
        params=[
            ShortcodeParam("first_arg"),
            ShortcodeParam("2"),
            ShortcodeParam('3rd "quoted"   arg'),
            ShortcodeParam("fourth"),
        ],
        closer=closer,
    )
    assert parsed.original_text == text


@pytest.mark.parametrize("closer", [True, False])
def test_shortcode_grammar_respects_spaces_in_quoted_named_params(closer):
    symbol = "/" if closer else ""
    text = f'{{{{<{symbol} some_name one=first_arg two=2 and_three="3rd \\"quoted\\"   arg" param_4=fourth >}}}}'
    parser = ShortcodeParser()
    parsed = parser.parse_string(text)

    print("\n\n")
    for p in parsed.shortcode.params:
        print(p)

    assert parsed.shortcode == ShortcodeTag(
        "some_name",
        params=[
            ShortcodeParam(name="one", value="first_arg"),
            ShortcodeParam(name="two", value="2"),
            ShortcodeParam(name="and_three", value='3rd "quoted"   arg'),
            # Check a shortcode name with a number in it.
            ShortcodeParam(name="param_4", value="fourth"),
        ],
        closer=closer,
    )
    assert parsed.original_text == text


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

    assert quoted.shortcode == ShortcodeTag(
        "fake_shortcode",
        params=[ShortcodeParam("uuid"), ShortcodeParam("{{< sup 4 >}}")],
    )
    assert quoted.original_text == text_quoted

    # Here "sup" and "4" are captured as separate arguments.
    text_not_nested = R"{{< fake_shortcode uuid sup 4 >}}"
    not_nested = parser.parse_string(text_not_nested)
    assert not_nested.shortcode == ShortcodeTag(
        name="fake_shortcode",
        params=[ShortcodeParam("uuid"), ShortcodeParam("sup"), ShortcodeParam("4")],
    )
    assert not_nested.original_text == text_not_nested

    # "real" nesting raises an error:

    with pytest.raises(ValueError, match="nesting"):
        text_nested = R'{{< fake_shortcode uuid {{< sup 4 >}} "Cats and dogs" >}}'
        parser.parse_string(text_nested)


def test_shortcode_parser_parses_named_parameter_and_dashes():
    text = R'{{< image-gallery-item href="421516494150ff096b974c8f16c0086e_504693-01D.jpg" data-ngdesc="Kristen R leads a discussion" text="engineering is cool" >}}'
    parser = ShortcodeParser()
    parsed = parser.parse_string(text)

    assert parsed.shortcode == ShortcodeTag(
        name='image-gallery-item',
        params=[
            ShortcodeParam(
                name='href',
                value='421516494150ff096b974c8f16c0086e_504693-01D.jpg'
            ),
            ShortcodeParam(
                 name='data-ngdesc',
                 value='Kristen R leads a discussion',
            ),
            ShortcodeParam(
                name='text',
                value='engineering is cool'
            )
        ]
    )