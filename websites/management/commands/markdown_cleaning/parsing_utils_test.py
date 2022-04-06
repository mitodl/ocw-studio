import uuid

import pytest

from websites.management.commands.markdown_cleaning.parsing_utils import (
    unescape_quoted_string,
)
from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParam,
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
                name=shortcode.name, params=shortcode.params, percent_delimiters=True
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
        (
            R'''"quotes are \" \\\" \\\\\" ok "''',
            R"""quotes are " \\" \\\\" ok """,
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
        R'"missing escales\\" "' R'"missing escales\\\\" "',
    ],
)
def test_unescape_quoted_string_raises_value_errors(bad_text):
    with pytest.raises(ValueError):
        assert unescape_quoted_string(bad_text)


@pytest.mark.parametrize(
    ["closer", "percent_delimiters", "expected"],
    [
        (False, False, R'{{< my_shortcode "first" "second \"two\"   2" >}}'),
        (True, False, R'{{</ my_shortcode "first" "second \"two\"   2" >}}'),
        (False, True, R'{{% my_shortcode "first" "second \"two\"   2" %}}'),
        (True, True, R'{{%/ my_shortcode "first" "second \"two\"   2" %}}'),
    ],
)
def test_shortcode_positional_params(closer, percent_delimiters, expected):
    """Test creating shortcode objects with positional paramters."""
    shortocde = ShortcodeTag(
        name="my_shortcode",
        params=[ShortcodeParam("first"), ShortcodeParam('second "two"   2')],
        percent_delimiters=percent_delimiters,
        closer=closer,
    )
    assert shortocde.to_hugo() == expected


@pytest.mark.parametrize(
    ["closer", "percent_delimiters", "expected"],
    [
        (
            False,
            False,
            R'{{< my_shortcode one="first" and_two="second \"two\"   2" >}}',
        ),
        (
            True,
            False,
            R'{{</ my_shortcode one="first" and_two="second \"two\"   2" >}}',
        ),
        (False, True, R'{{% my_shortcode one="first" and_two="second \"two\"   2" %}}'),
        (True, True, R'{{%/ my_shortcode one="first" and_two="second \"two\"   2" %}}'),
    ],
)
def test_shortcode_named_params(closer, percent_delimiters, expected):
    """Test creating shortcode objects with named paramters."""
    shortocde = ShortcodeTag(
        name="my_shortcode",
        params=[
            ShortcodeParam(name="one", value="first"),
            ShortcodeParam(name="and_two", value='second "two"   2'),
        ],
        percent_delimiters=percent_delimiters,
        closer=closer,
    )
    assert shortocde.to_hugo() == expected


def test_shortcode_get_param():
    """
    Test retrieving shortcode params by name or position, similar to Hugo's .Get
    """
    s1 = ShortcodeTag(
        "my_shortcode",
        params=[
            ShortcodeParam(name="cat", value="meow"),
            ShortcodeParam(name="dog", value="bark_bark"),
        ],
    )
    s2 = ShortcodeTag(
        "my_shortcode",
        params=[ShortcodeParam(value="bark_bark"), ShortcodeParam(value="meow")],
    )

    assert s1.get(0) == "meow"
    assert s1.get(1) == "bark_bark"
    assert s1.get("cat") == "meow"
    assert s1.get("dog") == "bark_bark"

    assert s2.get(0) == "bark_bark"
    assert s2.get(1) == "meow"

    with pytest.raises(IndexError):
        s1.get(2)

    with pytest.raises(KeyError):
        s1.get("unicorn")

    with pytest.raises(IndexError):
        s2.get(2)

    with pytest.raises(KeyError):
        s2.get("cat")


@pytest.mark.parametrize(
    ["shortcode_param_values", "expected"],
    [
        ([], R"{{< meow >}}"),
        (["abc", "x y  z", 'f "g" h'], R'{{< meow "abc" "x y  z" "f \"g\" h" >}}'),
        (["Previous «« cool"], R'{{< meow "Previous «« cool" >}}'),
        (
            ["hugo", "does not permit \n newlines", "in shortcode arguments"],
            R'{{< meow "hugo" "does not permit   newlines" "in shortcode arguments" >}}',
        ),
    ],
)
def test_shortcode_serialization(shortcode_param_values, expected):
    params = [ShortcodeParam(s) for s in shortcode_param_values]
    shortocde = ShortcodeTag(name="meow", params=params)
    assert shortocde.to_hugo() == expected


def test_shortcode_resource_link():
    """
    Test that ShortcodeTag.resource_link creates correct resource_link shortcodes
    """
    id = uuid.uuid4()

    # no fragment supplied
    assert ShortcodeTag.resource_link(id, text="my text") == ShortcodeTag(
        name="resource_link",
        percent_delimiters=True,
        params=[ShortcodeParam(str(id)), ShortcodeParam("my text")],
    )

    # Empty string fragment
    assert ShortcodeTag.resource_link(id, text="my text", fragment="") == ShortcodeTag(
        name="resource_link",
        percent_delimiters=True,
        params=[ShortcodeParam(str(id)), ShortcodeParam("my text")],
    )

    # Empty string fragment
    assert ShortcodeTag.resource_link(
        id, text="my text", fragment="meow"
    ) == ShortcodeTag(
        name="resource_link",
        percent_delimiters=True,
        params=[
            ShortcodeParam(str(id)),
            ShortcodeParam("my text"),
            ShortcodeParam("#meow"),
        ],
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
    href_uuid = uuid.uuid4()

    assert ShortcodeTag.resource(id) == ShortcodeTag(
        name="resource",
        percent_delimiters=False,
        params=[ShortcodeParam(name="uuid", value=str(id))],
    )
    assert ShortcodeTag.resource(id, href_uuid=href_uuid) == ShortcodeTag(
        name="resource",
        percent_delimiters=False,
        params=[
            ShortcodeParam(name="uuid", value=str(id)),
            ShortcodeParam(name="href_uuid", value=str(href_uuid)),
        ],
    )

    assert ShortcodeTag.resource(id, href="/cats/go/meow") == ShortcodeTag(
        name="resource",
        percent_delimiters=False,
        params=[
            ShortcodeParam(name="uuid", value=str(id)),
            ShortcodeParam(name="href", value="/cats/go/meow"),
        ],
    )

    with pytest.raises(ValueError):
        ShortcodeTag.resource("bad uuid")

    with pytest.raises(ValueError):
        ShortcodeTag.resource(id, href_uuid=href_uuid, href="/cats/go/meow")
