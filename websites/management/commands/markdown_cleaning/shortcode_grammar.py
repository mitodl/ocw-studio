from dataclasses import dataclass, field
from pyparsing import nestedExpr, ParseResults

from websites.management.commands.markdown_cleaning.parsing_utils import (
    WrappedParser
)

def hugo_escape_shortcode_arg_if_necessary(s: str):
    """Double-quote and escape shortcode arg if necessary.

    Hugo shortcode arguments are space-separated, so arguments containing
    spaces must be double quoted. Hence quotes, too, must be escaped.
    """
    if ' ' in s or '"' in s:
        return '"' + s.replace('"', R'\"') + '"'
    return s

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
        args = ' '.join(hugo_escape_shortcode_arg_if_necessary(arg) for arg in self.args)
        return f'{self.opener} {self.name} {args} {self.closer}'


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