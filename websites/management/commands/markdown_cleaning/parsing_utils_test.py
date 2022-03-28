import uuid

import pytest

from websites.management.commands.markdown_cleaning.parsing_utils import (
    unescape_quoted_string,
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


@pytest.mark.parametrize(
    ["escaped", "unescaped"],
    [
        (R'''"cats \"and\" 'dogs' are cool."''', R"""cats "and" 'dogs' are cool."""),
        (
            R'''"special characters « and backslashes \ \" are \ ok"''',
            R"""special characters « and backslashes \ " are \ ok""",
        ),
        (R"""'cats \'and\' "dogs" are cool.'""", R"""cats 'and' "dogs" are cool."""),
        (
            R"""'special characters « and backslashes \ \' are \ ok'""",
            R"""special characters « and backslashes \ ' are \ ok""",
        ),
    ],
)
def test_unescape_quoted_string(escaped, unescaped):
    assert unescape_quoted_string(escaped) == unescaped


@pytest.mark.parametrize(
    "bad_text",
    [
        """cat""",
        """'cat""",
        """cat'""",
        """cat""",
        """"cat""",
        '''cat"''',
        '"missing "escapes" so sad "',
        "'missing 'escapes' so sad '",
    ],
)
def test_unescape_quoted_string_raises_value_errors(bad_text):
    with pytest.raises(ValueError):
        assert unescape_quoted_string(bad_text)

@pytest.mark.parametrize(
    "bad_text",
    [
        "' cat \\\\' dog '",
        '" cat \\\\" dog "'
    ],
)
def test_unescape_quoted_string_raises_not_implemented_errors(bad_text):
    with pytest.raises(NotImplementedError):
        assert unescape_quoted_string(bad_text)


@pytest.mark.parametrize(
    ["closer", "percent_delimiters", "expected"],
    [
        (False, False, R'{{< my_shortcode "first" "second   2" >}}'),
        (True, False, R'{{</ my_shortcode "first" "second   2" >}}'),
        (False, True, R'{{% my_shortcode "first" "second   2" %}}'),
        (True, True, R'{{%/ my_shortcode "first" "second   2" %}}'),
    ],
)
def test_shortcode(closer, percent_delimiters, expected):
    shortocde = ShortcodeTag(
        name="my_shortcode",
        args=["first", "second   2"],
        percent_delimiters=percent_delimiters,
        closer=closer,
    )
    assert shortocde.to_hugo() == expected


@pytest.mark.parametrize(
    ["shortcode_args", "expected"],
    [
        ([], R"{{< meow >}}"),
        (["abc", "x y  z", 'f "g" h'], R'{{< meow "abc" "x y  z" "f \"g\" h" >}}'),
        (["Previous «« cool"], R'{{< meow "Previous «« cool" >}}'),
    ],
)
def test_shortcode_serialization(shortcode_args, expected):
    shortocde = ShortcodeTag(name="meow", args=shortcode_args)
    assert shortocde.to_hugo() == expected


def test_shortcode_resource_link():
    """
    Test that ShortcodeTag.resource_link creates correct resource_link shortcodes
    """
    id = uuid.uuid4()

    # no fragment supplied
    assert ShortcodeTag.resource_link(id, text="my text") == ShortcodeTag(
        name="resource_link", percent_delimiters=True, args=[str(id), "my text"]
    )

    # Empty string fragment
    assert ShortcodeTag.resource_link(id, text="my text", fragment="") == ShortcodeTag(
        name="resource_link", percent_delimiters=True, args=[str(id), "my text"]
    )

    # Empty string fragment
    assert ShortcodeTag.resource_link(
        id, text="my text", fragment="meow"
    ) == ShortcodeTag(
        name="resource_link",
        percent_delimiters=True,
        args=[str(id), "my text", "#meow"],
    )

    with pytest.raises(ValueError):
        ShortcodeTag.resource_link("bad uuid", text="my text")

    with pytest.raises(TypeError):
        ShortcodeTag.resource_link(text="my text")


def test_shortcode_resource():
    """
    Test that ShortcodeTag.resource creates correct resource_link shortcodes
    """
    id = uuid.uuid4()

    # no fragment supplied
    assert ShortcodeTag.resource(id) == ShortcodeTag(
        name="resource", percent_delimiters=False, args=[str(id)]
    )

    with pytest.raises(ValueError):
        ShortcodeTag.resource("bad uuid")
