from dataclasses import dataclass, field
from pyparsing import nestedExpr

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

@dataclass
class ParsedShortcode:
    shortcode: Shortcode
    original_text: str

def find_nth(string: str, sub: str, n, start = 0):
    """Find the nth occurence of `sub` in string starting from `start`."""
    i = start
    remaining = n
    found_at = -1
    while (remaining >= 0):
        found_at = string.find(sub, i)
        if found_at == -1: return -1
        i = found_at + len(sub)
        remaining -= 1
    return found_at

class ShortcodeParser:

    def __init__(self):

        def record_shortcode(percent_delimiters: bool):
            """
            Returns a pyparsing parse action that transforms the nestedExpr
            match into a ParsedShortcode object.
            """
            closer = R'%}}' if percent_delimiters else R'>}}'
            def _parse_action(s: str, l: int, toks: 'list[list[str]]'):
                if len(toks) > 1:
                    raise ValueError('Assumption violated. Investigate.')
                if any(not isinstance(s, str) for s in toks[0]):
                    raise ValueError('Unexpected shortcode nesting.')

                closer_count = ''.join(toks[0]).count(closer)
                start_index = l
                end_index = find_nth(s, closer, closer_count, l) + len(closer)
                name = toks[0][0]
                args = [self.hugo_unescape_shortcode_arg(s) for s in toks[0][1:]]
                shortcode = Shortcode(name, args, percent_delimiters)
                original_text = s[start_index: end_index]
                return ParsedShortcode(shortcode, original_text)
            return _parse_action

        angle_expr =nestedExpr(opener=R"{{<", closer=R">}}").setParseAction(record_shortcode(percent_delimiters=False))
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

    @staticmethod
    def hugo_unescape_shortcode_arg(s: str):
        return s.strip('"').replace('\\"', '"')