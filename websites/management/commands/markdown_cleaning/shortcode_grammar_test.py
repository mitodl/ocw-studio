import pytest

from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParser,
    ShortcodeTag,
    ShortcodeParam
)


@pytest.mark.parametrize(["closer"], [(True,), (False,)])
def test_shortcode_grammar_respects_spaces_in_quoted_arguments(closer):
    symbol = "/" if closer else ""
    text = f'{{{{<{symbol} some_name first_arg 2 "3rd \\"quoted\\"   arg" fourth >}}}}'
    parser = ShortcodeParser()
    parsed = parser.parse_string(text)

    assert parsed.shortcode == ShortcodeTag(
        "some_name",
        params=[ShortcodeParam(v)
        for v in ["first_arg", "2", '3rd "quoted"   arg', "fourth"]],
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
        "fake_shortcode", params=[ShortcodeParam("uuid"), ShortcodeParam("{{< sup 4 >}}")]
    )
    assert quoted.original_text == text_quoted

    # Here "sup" and "4" are captured as separate arguments.
    text_not_nested = R"{{< fake_shortcode uuid sup 4 >}}"
    not_nested = parser.parse_string(text_not_nested)
    assert not_nested.shortcode == ShortcodeTag(
        name="fake_shortcode", params=[ShortcodeParam("uuid"), ShortcodeParam("sup"), ShortcodeParam("4")]
    )
    assert not_nested.original_text == text_not_nested

    # "real" nesting raises an error:

    with pytest.raises(ValueError, match="nesting"):
        text_nested = R'{{< fake_shortcode uuid {{< sup 4 >}} "Cats and dogs" >}}'
        parser.parse_string(text_nested)
