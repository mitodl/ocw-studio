from dataclasses import dataclass
from typing import Union
from uuid import UUID

from pyparsing import ParserElement, ParseResults, originalTextFor


INITIAL_DEFAULT_WHITESPACE_CHARS = ParserElement.DEFAULT_WHITE_CHARS


def restore_initial_default_whitespace_chars():
    ParserElement.setDefaultWhitespaceChars(INITIAL_DEFAULT_WHITESPACE_CHARS)


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
        self.grammar.parseWithTabs()
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

    def parse_string(self, string: str, parse_all=True):
        """
        Snake-case alias for PyParsing's parseString.

        Note: The default value for parse_all (True) is different from
        Pyparsing.
        """
        return self.grammar.parseString(string, parseAll=parse_all)

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


def escape_double_quotes(s: str):
    """Encase `s` in double quotes and escape double quotes within `s`."""
    return s.replace('"', '\\"')


def unescape_string_quoted_with(text: str, single_quotes=False):
    """
    Given a string encased in quotes of type `quote_char` and in which all
    interior instances of `quote_char` are escaped, strip the encasing instances
    and unescape the interior instances.
    """
    q = "'" if single_quotes else '"'

    if f"\\\\{q}" in text:
        raise NotImplementedError(
            "Unescaping quoted strings in which backslashes precede quotes is not implemented."
        )

    all_escaped = text[1:-1].count(q) == text[1:-1].count(f"\\{q}")
    if text.startswith(q) and text.endswith(q) and all_escaped:
        return text[1:-1].replace(f"\\{q}", q)

    raise ValueError(f"{text} is not a valid single-quoted string")


def unescape_quoted_string(text: str):
    """
    Unescape a quoted string. That is:
        - if the string is single-quote-escaped, unescape all single quotes
        - if the string is double-quote-escaped, escape all double quotes

    Otherwise throws an error.
    """
    if text.startswith("'") and text.endswith("'"):
        return unescape_string_quoted_with(text, True)
    else:
        return unescape_string_quoted_with(text, False)


@dataclass
class ShortcodeTag:
    """
    Represents a shortcode tag.

    The general dataclass imposes very few limitations, e.g., any shortcode name
    is allowed and any number of arguments is allowed.

    Avoid direct use for creating new shortocdes. Instead, use convenience
    methods ShortcodeTag.resource and ShortcodeTag.resource_link. Add more as
    needed.
    """

    name: str
    args: "list[str]"
    percent_delimiters: bool = False
    closer: bool = False

    def get_delimiters(self):
        if self.percent_delimiters:
            opening_delimiter = "{{%"
            closing_delimiter = "%}}"
        else:
            opening_delimiter = "{{<"
            closing_delimiter = ">}}"

        if self.closer:
            opening_delimiter += "/"

        return opening_delimiter, closing_delimiter

    def to_hugo(self):
        """
        Encases all shortcode arguments in double quotes, because Hugo allows it and that's simplest.
        """
        opening_delimiter, closing_delimiter = self.get_delimiters()
        pieces = [
            opening_delimiter,
            self.name,
            *(self.hugo_escape(arg) for arg in self.args),
            closing_delimiter,
        ]
        return " ".join(pieces)

    @staticmethod
    def hugo_escape(s: str):
        return f'"{escape_double_quotes(s)}"'

    @classmethod
    def resource_link(cls, uuid: Union[str, UUID], text: str, fragment=""):
        """Convenience method to create valid resource_link ShortcodeTag objects."""
        cls.validate_uuid(uuid)
        args = [str(uuid), text]
        if fragment:
            args.append("#" + fragment)

        return cls(
            name="resource_link",
            percent_delimiters=True,
            args=args,
        )

    @classmethod
    def resource(cls, uuid: Union[str, UUID]):
        """Convenience method to create valid resource_link ShortcodeTag objects."""
        cls.validate_uuid(uuid)
        return cls(name="resource", percent_delimiters=False, args=[str(uuid)])

    @staticmethod
    def validate_uuid(uuid: Union[str, UUID]) -> None:
        if not isinstance(uuid, UUID):
            UUID(uuid)
