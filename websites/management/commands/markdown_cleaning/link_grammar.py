from dataclasses import dataclass, field
from pyparsing import nestedExpr, Optional, originalTextFor, White, CharsNotIn, quotedString, StringEnd, ParseResults, Literal
from websites.management.commands.markdown_cleaning.parsing_utils import WrappedParser


@dataclass
class MarkdownLink:
    """
    Representation of a markdown link OR image.
    """
    text: str
    destination: str
    is_image: bool = False
    title: str = ''

    # Tuple of tuples (ParseResults, start_index, end_index) where 
    # - ParseResult has named tokens
    #       - link: MarkdownLinkOrImage
    #       - original_text: str
    # - start_index, end_index are the start/end of this link within self.text
    text_links: list = field(default_factory=tuple)

    def to_markdown(self):
        """Generate markdown representation of this link/image."""
        sep = ' ' if self.title else ''
        prefix = '!' if self.is_image else ''
        return f'{prefix}[{self.text}]({self.destination}{sep}"{self.title}"'

class LinkParser(WrappedParser):
    """
    Parser for markdown links and images.

    Why bother? Because a regex-based approach can have troubles when
        - link text/titles contain square brackets / parentheses
        - or when links are nested

    About nesting... According to CommonMark 0.30:
        - Link text should not contain links
            - Images are not expressly forbidden. Are they allowed? Unclear.
        - Image text CAN contain links

    This link parser is not quite CommonMark compliant... E.g., the grammar does
    not allow "at most one line end character" in the separator between link
    destination and link title, nor is the angle-bracket destination variant
    treated properly.
    """

    def __init__(self):

        is_image = Optional('!').setResultsName('is_image').setParseAction(lambda s, l, toks: bool(toks))
        text = originalTextFor(
                nestedExpr(
                    opener='[',
                    closer=']',
                    ignoreExpr=quotedString | Literal('\\[') | Literal('\\]')
                    )
            ).setResultsName('text')
        text.addParseAction(lambda s, l, toks: toks[0][1:-1])
        back = originalTextFor(nestedExpr(opener='(', closer=')')).addParseAction(lambda s, l, toks: toks[0][1:-1])

        back_parser = (
            Optional(CharsNotIn(' \t')).setResultsName('destination')
            +
            Optional(
                White(' ') +
                quotedString.copy().setResultsName('title').setParseAction(lambda _s, _l, t: t[0][1:-1])
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
            if '](' in text:
                text_links = tuple(self.scan_string(text))
            else:
                text_links = tuple()

            link = MarkdownLink(
                text=text,
                destination=destination,
                title=title,
                is_image=is_image,
                text_links=text_links
            )

            return ParseResults.from_dict({"link": link})

        grammar.setParseAction(parse_action)

        super().__init__(grammar)
