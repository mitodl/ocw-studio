from dataclasses import dataclass, field
from pyparsing import nestedExpr, Forward, Word

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
        args = ' '.join(self.args)
        return f'{self.opener} {self.name} {args} {self.closer}'

class ShortcodeParser:

    def __init__(self):

        def record_shortcode(percent_delimiters: bool):
            def _parse_action(_s: str, _l: int, toks):
                return Shortcode(toks[0][0], toks[0][1:], percent_delimiters)
            return _parse_action

        angle_expr = nestedExpr(opener=R"{{<", closer=R">}}").setParseAction(record_shortcode(percent_delimiters=False))
        percent_expr = nestedExpr(opener=R"{{%", closer=R"%}}").setParseAction(record_shortcode(percent_delimiters=True))

        self.angle_expr = angle_expr
        self.percent_expr = percent_expr
        self.grammar = angle_expr | percent_expr


    def add_parse_action(self, parse_action):
        """
        Add a parse action that will be called for each shortcode match.
        """

        # Add to the two shortcode variants separately. Otherwise the parse
        # action is only called for the outermost match.
        # (Which probably wouldn't be a big deal, since they should
        # not be nested anyway.)
        self.angle_expr.addParseAction(parse_action)
        self.percent_expr.addParseAction(parse_action)

    def parse_string(self, string: str):
        """
        Snake-case alias for PyParsing's parseString.
        """
        return self.grammar.parseString(string)

    def transform_string(self, string: str):
        """
        Snake-case alias for PyParsing's transformString
        """
        return self.grammar.transformString(string)
