from unittest.mock import Mock

import pytest
from pyparsing import ParseException
from websites.management.commands.markdown_cleaning.link_grammar import (
    LinkParser,
    MarkdownLink
)

@pytest.mark.parametrize('is_image', [True, False,])
@pytest.mark.parametrize('text', [
    '',
    'some title with escaped \\] bracket and "quoted ]" brackets',
    'title with     whitespace',
    'linklike [] [] [cool]() title',
])
@pytest.mark.parametrize('dest', ['', '/some/destination/url', './and/this',])
@pytest.mark.parametrize('title', ['', 'my \\"favorite\\"   [title](here)',])
def test_link_parser_parses_good_links(title, dest, text, is_image):
    with_title = "" if not title else f' "{title}"'
    markdown = f"[{text}]({dest}{with_title})"

    if is_image:
        markdown = '!' + markdown
    parser = LinkParser()
    parsed = parser.parse_string(markdown)
    assert parsed.original_text == markdown

    expected_link = MarkdownLink(
        text=text,
        destination=dest,
        title=title,
        is_image=is_image,
        # Set the two text_links equal. We'll test this separately later.
        text_links=parsed.link.text_links
    )
    assert parsed.link == expected_link

@pytest.mark.parametrize('markdown', [
    'no link here',
    '',
    '[unbalcned] square brackets](url)'
    '[not a link] but [this is](url)'
    '[ unbalanced] ](blarg)',
    '[some text](too "many" "things")',
    '[some text](./path/to/thing no_quotation_marks_around_title)'
])
def test_link_parser_rejects_bad_links(markdown):
    parser = LinkParser()
    with pytest.raises(ParseException):
        parser.parse_string(markdown)

def test_link_parser_with_nesting():
    text = '[some text ![image [another](why) [oh dear](whywhy) text](imageurl) and more ](path/to/thing "with (title?)")'
    parser = LinkParser()
    action = Mock(wraps=lambda s, l, toks: toks)
    parser.set_parse_action(action)

    parsed = parser.parse_string(text)

    expected_outer_link = MarkdownLink(
        text='some text ![image [another](why) [oh dear](whywhy) text](imageurl) and more ',
        destination='path/to/thing',
        title='with (title?)',
    )
    expected_middle_link = MarkdownLink(
        text='image [another](why) [oh dear](whywhy) text',
        destination='imageurl',
        is_image=True,
    )
    expected_inner_link1 = MarkdownLink(text='another', destination='why')
    expected_inner_link2 = MarkdownLink(text='oh dear', destination='whywhy')

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
