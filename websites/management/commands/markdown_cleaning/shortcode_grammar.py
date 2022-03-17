import json

from dataclasses import dataclass, field
from pyparsing import nestedExpr, ParseResults

from websites.management.commands.markdown_cleaning.parsing_utils import (
    WrappedParser
)

@dataclass
class Shortcode:
    name: str
    args: 'list[str]'
    opener: str = field(init=False)
    closer: str = field(init=False)
    percent_delimiters: bool = False\

    def __post_init__(self):
        if self.percent_delimiters:
            self.opener = '{{%'
            self.closer = '%}}'
        else:
            self.opener = '{{<'
            self.closer = '>}}'

    def to_hugo(self):
        pieces = [self.opener, self.name, *(self.hugo_escape(arg) for arg in self.args), self.closer]
        return ' '.join(pieces)
    
    @staticmethod
    def hugo_escape(s: str):
        return json.dumps(s)


class ShortcodeParser(WrappedParser):

    def __init__(self):

        def record_shortcode(percent_delimiters: bool):
            """
            Returns a pyparsing parse action that transforms the nestedExpr
            match into a ParsedShortcode object.
            """
            def _parse_action(s: str, l: int, toks: 'list[list[str]]'):
                if len(toks) > 1:
                    raise ValueError('Assumption violated. Investigate.')
                if any(not isinstance(s, str) for s in toks[0]):
                    raise ValueError('Unexpected shortcode nesting.')

                name = toks[0][0]
                args = [self.hugo_unescape_shortcode_arg(s) for s in toks[0][1:]]
                shortcode = Shortcode(name, args, percent_delimiters)
                return ParseResults.from_dict({"shortcode": shortcode})
            return _parse_action

        angle_expr =nestedExpr(opener=R"{{<", closer=R">}}").setParseAction(record_shortcode(percent_delimiters=False))
        percent_expr = nestedExpr(opener=R"{{%", closer=R"%}}").setParseAction(record_shortcode(percent_delimiters=True))

        grammar = angle_expr | percent_expr
        super().__init__(grammar)

    @staticmethod
    def hugo_unescape_shortcode_arg(s: str):
        return s.strip('"').replace('\\"', '"')