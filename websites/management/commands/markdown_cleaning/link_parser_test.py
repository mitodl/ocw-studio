from unittest.mock import Mock

import pytest
from pyparsing import ParseException

from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    MarkdownLink,
)


@pytest.mark.parametrize("text", ["", "simple text", "a [bit] \\] more complex"])
@pytest.mark.parametrize("dest", ["", "./path/to/thing"])
@pytest.mark.parametrize(
    ["title", "expected_suffix"],
    [("", ""), ('cats "and" dogs', ' "cats \\"and\\" dogs"')],
)
@pytest.mark.parametrize("is_image", [True, False])
def test_markdown_link_serialization(is_image, title, expected_suffix, dest, text):
    link = MarkdownLink(text=text, destination=dest, title=title, is_image=is_image)
    expected = f"[{text}]({dest}{expected_suffix})"
    if is_image:
        expected = "!" + expected

    assert link.to_markdown() == expected


def test_markdown_link_serialization_more_expliclity():
    without_title = MarkdownLink(
        text="some text", destination="path/to/thing", title="", is_image=False
    )

    assert without_title.to_markdown() == "[some text](path/to/thing)"

    with_title = MarkdownLink(
        text="some text",
        destination="path/to/thing",
        title='Markdown is so "fun" right',
        is_image=True,
    )

    assert (
        with_title.to_markdown()
        == '![some text](path/to/thing "Markdown is so \\"fun\\" right")'
    )


@pytest.mark.parametrize("is_image", [True, False])
@pytest.mark.parametrize(
    "text",
    [
        "",
        "some title with escaped \\] opening and closing \\[  brackets",
        "title with     whitespace",
        "title with\nsingle\nnewlines",
        "linklike [] [] [cool]() title",
    ],
)
@pytest.mark.parametrize("dest", ["", "/some/dest/url", "./and/this"])
@pytest.mark.parametrize("title", ["", "my favorite  [title](here)"])
def test_link_parser_parses_good_links(title, dest, text, is_image):
    with_title = "" if not title else f' "{title}"'
    markdown = f"[{text}]({dest}{with_title})"

    if is_image:
        markdown = "!" + markdown
    parser = LinkParser()
    parsed = parser.parse_string(markdown)
    assert parsed.original_text == markdown

    expected_link = MarkdownLink(
        text=text,
        destination=dest,
        title=title,
        is_image=is_image,
        # Set the two text_links equal. We'll test this separately later.
        text_links=parsed.link.text_links,
    )
    assert parsed.link == expected_link


def test_link_parser_with_tabs():
    """
    Pyparsing's default behavior is to replace tabs with spaces.
    """
    parser = LinkParser()
    parsed = parser.parse_string("[a\tb](url)")
    assert parsed.link.text == "a\tb"


def test_link_parser_with_shortcodes_in_destination():
    """Test that the parser allows shortcodes in the destination.

    The reason this is a little special is that shortcodes can have spaces
    whereas usually that's not allowed in the destination.
    """
    markdown1 = R"[some text]({{< baseurl >}}/path/to/thing)"
    parser = LinkParser()
    parsed1 = parser.parse_string(markdown1)
    assert parsed1.link == MarkdownLink(
        text="some text", destination=R"{{< baseurl >}}/path/to/thing"
    )

    markdown2 = R'[some text]({{< baseurl >}}/path/to/thing "some title")'
    parsed2 = parser.parse_string(markdown2)
    assert parsed2.link == MarkdownLink(
        text="some text",
        destination=R"{{< baseurl >}}/path/to/thing",
        title="some title",
    )

    markdown3 = R'[some text](/front_text{{< baseurl >}}/path/to/thing "some title")'
    parsed3 = parser.parse_string(markdown3)
    assert parsed3.link == MarkdownLink(
        text="some text",
        destination=R"/front_text{{< baseurl >}}/path/to/thing",
        title="some title",
    )


@pytest.mark.parametrize(
    "markdown",
    [
        "no link here",
        "",
        "[unbalcned] square brackets](url)"
        "[not a link] but [this is](url)"
        "[ unbalanced] ](blarg)",
        '[some text](too "many" "things")',
        "[some text](./path/to/thing no_quotation_marks_around_title)",
        "[cat\n\ndog](meow)",
        "[cat\n  \t  \ndog](meow)",
        "[cat\n \n \t  \ndog](meow)",
        "[cat\n  \t  \n](meow)",
        "[\n   \t  \n cat](meow)",
        "[\n   \t \n](meow)",
        "[bracket in ']' quotes](meow)",
        '[bracket in "]" quotes](meow)',
    ],
)
def test_link_parser_rejects_bad_links(markdown):
    parser = LinkParser()
    with pytest.raises(ParseException):
        parser.parse_string(markdown)


def test_link_parser_titles_with_quotes():
    markdown = '[markdown](it/is "so \\"fun\\" right?")'
    parser = LinkParser()
    parsed = parser.parse_string(markdown)

    assert parsed.original_text == markdown
    assert parsed.link == MarkdownLink(
        text="markdown",
        destination="it/is",
        title='so "fun" right?',
        text_links=tuple(),
    )


def test_link_parser_with_nesting():
    text = '[some text ![image [another](why) [oh dear](whywhy) text](imageurl) and more ](path/to/thing "with (title?)")'
    parser = LinkParser()
    action = Mock(wraps=lambda s, l, toks: toks)
    parser.set_parse_action(action)

    parsed = parser.parse_string(text)

    expected_outer_link = MarkdownLink(
        text="some text ![image [another](why) [oh dear](whywhy) text](imageurl) and more ",
        destination="path/to/thing",
        title="with (title?)",
    )
    expected_middle_link = MarkdownLink(
        text="image [another](why) [oh dear](whywhy) text",
        destination="imageurl",
        is_image=True,
    )
    expected_inner_link1 = MarkdownLink(text="another", destination="why")
    expected_inner_link2 = MarkdownLink(text="oh dear", destination="whywhy")

    outer = parsed
    assert outer.link.text == expected_outer_link.text
    assert outer.link.destination == expected_outer_link.destination
    assert outer.link.title == expected_outer_link.title
    assert outer.link.is_image == expected_outer_link.is_image

    assert len(outer.link.text_links) == 1
    middle, middle_start, middle_end = outer.link.text_links[0]

    assert outer.link.text[middle_start:middle_end] == middle.original_text

    assert middle.link.text == expected_middle_link.text
    assert middle.link.destination == expected_middle_link.destination
    assert middle.link.title == expected_middle_link.title
    assert middle.link.is_image == expected_middle_link.is_image

    assert outer.link.text[middle_start:middle_end] == middle.original_text

    inner1, inner1_start, inner1_end = middle.link.text_links[0]
    inner2, inner2_start, inner2_end = middle.link.text_links[1]

    assert len(middle.link.text_links) == 2

    assert middle.link.text[inner1_start:inner1_end] == inner1.original_text
    assert middle.link.text[inner2_start:inner2_end] == inner2.original_text

    assert inner1.link == expected_inner_link1
    assert inner2.link == expected_inner_link2

    assert action.call_count == 4
