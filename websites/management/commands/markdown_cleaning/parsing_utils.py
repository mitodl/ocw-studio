import json
from pyparsing import ParseResults, originalTextFor

class WrappedParser:
    """
    Wrapper around Pyparsing grammars.

    This serves two purposes:
        1. Ensure availability of the original text for individual matches
            on parse actions.
        2. Provide nice snake_case names. Our version of Pyparsing does not have
            snake case names. (It's introduce in 3.0; we're on 2.4.7)
    """

    def __init__(self, grammar) -> None:

        self.grammar = originalTextFor(grammar)
        self.set_parse_action()

    @staticmethod
    def _original_text_for(s: str, _l: int, toks):
        original_text = s[toks.pop("_original_start") : toks.pop("_original_end")]
        results = toks.asDict()
        results["original_text"] = original_text
        return ParseResults.from_dict(results)

    def set_parse_action(self, *parse_actions):
        """
        Set parse actions to on the wrapped grammar. These will be called with
        arguments
            - s (str): the *entire* original string
            - l (int): starting index of match within s
            - toks (ParseResults): A ParseResults object with properties
                - original_text: the original text for *this* match
                - ...: and any named properties on parse results of the underlying
                    grammar.
        """
        self.grammar.setParseAction(self._original_text_for)
        self.grammar.addParseAction(*parse_actions)

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

    def scan_string(self, string: str):
        """
        Snake-case alias for Pyparsing's scanString
        """
        return self.grammar.scanString(string)

def standardize_title(s, l, toks):
    text: str = toks[0]
    if text.startswith("'") and text.endswith("'"):
        double_quoted = (
            text[1:-1]              # remove the outer single quote
            .replace("\\'", "'")    # unescape single quotes
            .replace('"', '\\"')    # escape double quotes
        )
        return json.loads(double_quoted)
    elif text.startswith('"')  and text.endswith('"'):
        return json.loads(text[1:-1])

def unescape_single_quoted_string(text: str):
    """
    Unescape quotes in a string that:
        - is encased in single quotes
        - in which all inner single quotes are backslash escaped
    """
    all_escaped = text[1:-1].count("'") == text[1:-1].count('\\"')
    if text.startswith("'") and text.endswith("'") and all_escaped:
        double_quoted = '"' + (
            text[1:-1]              # remove the outer single quote
            .replace("\\'", "'")    # unescape single quotes
            .replace('"', '\\"')    # escape double quotes
        ) + '"'
        try:
            decoded = json.loads(double_quoted)
            if isinstance(decoded, str):
                return decoded 
        except json.decoder.JSONDecodeError:
            pass

    raise ValueError(f"{text} is not a valid single-quoted string")

def unescape_double_quoted_string(text: str):
    """
    Unescape quotes and backslashes in a string that:
        - is encased in double quotes
        - in which all inner double quotes are backslash escaped
        - in which backslashes are backslash-escaped
    """
    try:
        decoded = json.loads(text)
        if isinstance(decoded, str):
            return decoded 
    except json.decoder.JSONDecodeError as err:
        raise ValueError(f"{text} is not a valid double-quoted string") from err

def unescape_quoted_string(text: str):
    """
    Unescape a quoted string. That:
        - if the string is single-quote-escaped, unescape all single quotes
        - if the string is double-quote-escaped, escape all double quotes

    Otherwise throws an error.
    """
    if text.startswith("'") and text.endswith("'"):
        return unescape_single_quoted_string(text)
    else:
        return unescape_double_quoted_string(text)