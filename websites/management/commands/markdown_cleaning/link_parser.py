from email.parser import Parser
import json
from dataclasses import dataclass, field

from pyparsing import (
    CharsNotIn,
    Literal,
    Optional,
    ParseResults,
    StringEnd,
    White,
    NotAny,
    nestedExpr,
    originalTextFor,
    quotedString,
    OneOrMore,
    FollowedBy,
    Word,
    ParserElement,
    Combine,
    ZeroOrMore,
)

from websites.management.commands.markdown_cleaning.parsing_utils import (
    WrappedParser,
    unescape_quoted_string,
    restore_initial_default_whitespace_chars,
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

        # Pylint is having trouble with unary operators on PyParsing elements.
        # pylint: disable=invalid-unary-operand-type

        is_image = (
            Optional("!")
            .setResultsName("is_image")
            .setParseAction(lambda s, l, toks: bool(toks))
        )
        double_line_break = (
            Word("\n\r", exact=1) + Optional(Word(" \t")) + Word("\n\r", exact=1)
        )

        text_ignore = Literal("\\[") | Literal("\\]")
        text_content = Combine(
            OneOrMore(
                ~text_ignore
                + FollowedBy(~double_line_break)
                + CharsNotIn("[]", exact=1)
            )
            + ~double_line_break
        )
        text = originalTextFor(
            nestedExpr(
                opener="[",
                closer="]",
                content=text_content,
                ignoreExpr=text_ignore,
            )
        ).setResultsName("text")
        text.addParseAction(lambda s, l, toks: toks[0][1:-1])

        back = originalTextFor(nestedExpr(opener="(", closer=")")).addParseAction(
            lambda s, l, toks: toks[0][1:-1]
        )

        back_parser = (
            Combine(
                ZeroOrMore(
                    originalTextFor(nestedExpr(opener=R"{{<", closer=">}}"))
                    | originalTextFor(nestedExpr(opener=R"{{%", closer="%}}"))
                    | CharsNotIn(" \t", exact=1)
                )
            )
            .setWhitespaceChars("")  # can't gobble the whitespace,
            .setResultsName("destination")
            + Optional(
                White(" ")
                +
                # CommonMark requires link title to be encased in single-quotes,
                # double-quotes, or wrapped in parentheses. Let's not bother with
                # the parentheses case for now.
                quotedString.copy()
                .setResultsName("title")
                .setParseAction(lambda s, l, toks: unescape_quoted_string(toks[0]))
            )
            + StringEnd()
        )

        def back_parse_action(_s, _l, toks):
            if " " in toks[0]:
                return back_parser.parseString(toks[0])
            return ParseResults.from_dict({"destination": toks[0]})

        back.addParseAction(back_parse_action)

        grammar = is_image + text + back

        def parse_action(_s, _l, toks):
            token = toks
            is_image = token.is_image
            title = token.title
            text = token.text
            destination = token.destination

            # Use self.scan_string not grammar.scan_string
            # so that parse actions attached to LinkParser fire for the nested
            # links, which seems desirable.
            if "](" in text:
                text_links = tuple(self.scan_string(text))
            else:
                text_links = tuple()

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
