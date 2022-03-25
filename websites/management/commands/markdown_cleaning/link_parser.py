import json
from dataclasses import dataclass, field
from typing import Protocol

from pyparsing import (
    CharsNotIn,
    Combine,
    FollowedBy,
    Literal,
    Optional,
    ParserElement,
    ParseResults,
    StringEnd,
    White,
    Word,
    ZeroOrMore,
    nestedExpr,
    originalTextFor,
    quotedString,
)

from websites.management.commands.markdown_cleaning.parsing_utils import (
    WrappedParser,
    restore_initial_default_whitespace_chars,
    unescape_quoted_string,
)


@dataclass
class MarkdownLink:
    """
    Representation of a markdown link OR image.
    """

    text: str
    destination: str
    is_image: bool = False
    title: str = ""

    # Tuple of tuples (ParseResults, start_index, end_index) where
    # - ParseResult has named tokens
    #       - link: MarkdownLinkOrImage
    #       - original_text: str
    # - start_index, end_index are the start/end of this link within self.text
    text_links: list = field(default_factory=tuple)

    def to_markdown(self):
        """Generate markdown representation of this link/image."""
        prefix = "!" if self.is_image else ""
        title_suffix = " " + json.dumps(self.title) if self.title else ""
        return f"{prefix}[{self.text}]({self.destination}{title_suffix})"

class LinkParseResult(Protocol):

    link: MarkdownLink
    original_text: str


class LinkParser(WrappedParser):
    """
    Parser for markdown links and images.

    Why bother?
    ===========

    Consider a naive regex appraoch:

    >>> import re
    >>> link = re.compile(r'\[(?P<text>.*?)\]\(?<dest>.*?\)')
    >>> first = link.search('See [Reference 1] blah balh [some text](url)')
    >>> first.group('text')
    'Reference 1] blah balh [some text'

    Way too much text has been captured.

    Of course, we can forbid the `text` group from containing square brackets.
    But then we won't match links whose titles contain square brackets! Markdown
    link text (in CommonMark) is allowed to contain any sequence of balanced
    square brackets, something regex simply can't handle.

    So to robustly parse Markdown links, we can't use regex.

    Speaking of CommonMark: (https://spec.commonmark.org/0.30/#links)
    The link spec has lots of edge cases. This parser is not fully compliant.
    For example, the grammar does not allow "at most one line end character" in
    the separator between link destination and link title, nor is the
    angle-bracket destination variant treated properly.
    """

    def __init__(self):

        # By default pyparsing collapses whitespace characters.
        # Markdown cares about whitespace containing double newlines, so we
        # can't collapse newlines.
        ParserElement.setDefaultWhitespaceChars("")
        grammar = (
            self._parser_piece_is_image()
            + self._parser_piece_text()
            + self._parser_piece_destination_and_title()
        )

        def parse_action(_s, _l, toks):
            token = toks
            is_image = token.is_image
            title = token.title
            text = token.text
            destination = token.destination

            # Use self.scan_string not grammar.scan_string
            # so that parse actions attached to LinkParser fire for the nested
            # links, which seems desirable.
            text_links = tuple(self.scan_string(text))

            link = MarkdownLink(
                text=text,
                destination=destination,
                title=title,
                is_image=is_image,
                text_links=text_links,
            )

            return ParseResults.from_dict({"link": link})

        grammar.setParseAction(parse_action)

        restore_initial_default_whitespace_chars()

        super().__init__(grammar)

    @staticmethod
    def _parser_piece_is_image():
        """
        Return PyParsing element to match an optional ! at beginning of links
        to indicate that the link is actually an image.
        """
        is_image = (
            Optional("!")
            .setResultsName("is_image")
            .setParseAction(lambda s, l, toks: bool(toks))
        )
        return is_image

    @staticmethod
    def _parser_piece_text():
        """
        Return PyParsing element to the text of a markdown link.
        """
        # No double line breaks in markdown links
        double_line_break = (
            Word("\n\r", exact=1) + Optional(Word(" \t")) + Word("\n\r", exact=1)
        )

        # We will ignore escaped square brackets when match finding balanced
        # square brackets.
        ignore = Literal("\\[") | Literal("\\]")

        # The text parser will match text inside balanced brackets using the
        # nestedExpr helper function from PyParsing.
        #
        # Next we define the content that is allowed inside the brackets.
        content_character = ~FollowedBy(double_line_break) + CharsNotIn("[]", exact=1)
        # Normally with nestedExpr, the content parser would be separately applied
        # to each whitespace-separated string within the nested expression.
        # However, since we set whitespaceChars to '', the content parser is
        # applied to characters one-at-a-time.
        #
        # If this ever changes, we would need to change content to something
        # like Combine(OneOrMore(~ignore + content_character))
        content = content_character
        text = originalTextFor(
            nestedExpr(
                opener="[",
                closer="]",
                content=content,
                ignoreExpr=ignore,
            )
        ).setResultsName("text")
        text.addParseAction(lambda s, l, toks: toks[0][1:-1])
        return text

    @staticmethod
    def _parser_piece_destination_and_title():
        """
        Return PyParsing element to match the destination and title of a
        markdown link.
        """

        # Capture everything between the balanced parentheses
        # Then parse it later.
        dest_and_title = originalTextFor(
            nestedExpr(opener="(", closer=")")
        ).addParseAction(lambda s, l, toks: toks[0][1:-1])

        destination = Combine(
            # Zero or more non-space characters.
            # But before each character (exact=1) check if we have a
            # shortcode. If we do, allow that.
            ZeroOrMore(
                originalTextFor(nestedExpr(opener=R"{{<", closer=">}}"))
                | originalTextFor(nestedExpr(opener=R"{{%", closer="%}}"))
                | CharsNotIn(" \t", exact=1)
            )
        ).setResultsName("destination")

        # CommonMark requires link title to be encased in single-quotes,
        # double-quotes, or wrapped in parentheses. Let's not bother with
        # the parentheses case for now.
        title = (
            quotedString.copy()
            .setResultsName("title")
            .setParseAction(lambda s, l, toks: unescape_quoted_string(toks[0]))
        )

        # This will parse the contents of dest_and_title
        dest_and_title_parser = destination + Optional(White(" ") + title) + StringEnd()

        def back_parse_action(_s, _l, toks):
            return dest_and_title_parser.parseString(toks[0])

        dest_and_title.addParseAction(back_parse_action)

        return dest_and_title
