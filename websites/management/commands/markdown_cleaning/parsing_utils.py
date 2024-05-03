import re
from dataclasses import dataclass
from typing import ClassVar, Optional, Union
from uuid import UUID

from pyparsing import ParserElement, ParseResults, originalTextFor

import main.utils

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

    def parse_string(self, string: str, parse_all=True):  # noqa: FBT002
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


def unescape_string_quoted_with(text: str, single_quotes=False):  # noqa: FBT002
    """
    Given a string encased in quotes and in which all interior quote characters
    are escaped, strip the encasing quotes and unescape the interior quotes.

    By default, the quotation character is a double quotation mark.
    Use `singleQuotes=true` for single quotes.
    """
    q = "'" if single_quotes else '"'

    escaped_quote_regex = re.compile(
        r"(?<!\\)"  # anything except a backslash WITHOUT advancing match position  # noqa: E501, ISC003
        + r"(\\\\)*\\"  # an odd number of backlsashes
        + q  # a quote
    )

    def unescape(match: re.Match):
        return match[0].replace(f"\\{q}", q)

    quote_count = text[1:-1].count(q)
    escaped_quote_count = len(escaped_quote_regex.findall(text[1:-1]))
    all_escaped = quote_count == escaped_quote_count

    if text.startswith(q) and text.endswith(q) and all_escaped:
        return escaped_quote_regex.sub(unescape, text[1:-1])

    msg = f"{text} is not a valid {q}-quoted string"
    raise ValueError(msg)


def unescape_quoted_string(text: str):
    """
    Unescape a quoted string. That is:
        - if the string is single-quote-escaped, unescape all single quotes
        - if the string is double-quote-escaped, escape all double quotes

    Otherwise throws an error.
    """
    if text.startswith("'") and text.endswith("'"):
        return unescape_string_quoted_with(text, True)  # noqa: FBT003
    else:
        return unescape_string_quoted_with(text, False)  # noqa: FBT003


@dataclass
class ShortcodeParam:
    value: str
    name: Union[str, None] = None

    param_regex: ClassVar[re.Pattern] = re.compile(
        r"^((?P<name>[0-9a-zA-Z_\-]+)=)?(?P<value>.*)$"
    )

    @classmethod
    def from_hugo(cls, s: str):
        """
        Create a ShortcodeParam object from assignment string. Parameter value
        will be unescaped.

        Examples
        ========
        >>> ShortcodeParam.from_hugo('dog="woof \\"woof\\" bark"')
        ShortcodeParam(name='dog', value='woof "woof" bark')
        """
        match = cls.param_regex.match(s)
        name = match.group("name")
        value = cls.hugo_unescape_shortcode_param_value(match.group("value"))
        return cls(name=name, value=value)

    def to_hugo(self):
        """
        Convert a ShortcodeParam to text expected by hugo. Always encloses the
        value in double quotes and performs escapes on the inner text if necessary.

        Example
        =======
        >>> ShortcodeParam(name='dog', value='woof "woof" bark').to_hugo()
        'dog="woof \\"woof\\" bark"
        """
        hugo_value = self.hugo_escape_param_value(self.value)

        if self.name:
            return f"{self.name}={hugo_value}"
        return hugo_value

    @staticmethod
    def hugo_unescape_shortcode_param_value(s: str):
        quoted = '"' + s.strip('"') + '"'
        return unescape_quoted_string(quoted)

    @staticmethod
    def hugo_escape_param_value(s: str):
        """
        Make shortcode parameter safe for Hugo.
            - encase in double quotes and escape any quotes in the arg
            - replace newlines with space
        """
        no_new_lines = s.replace("\n", " ")
        return f'"{escape_double_quotes(no_new_lines)}"'


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
    params: "list[ShortcodeParam]"
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
        """  # noqa: E501
        opening_delimiter, closing_delimiter = self.get_delimiters()
        pieces = [
            opening_delimiter,
            self.name,
            *(p.to_hugo() for p in self.params),
            closing_delimiter,
        ]
        return " ".join(pieces)

    @classmethod
    def resource_link(
        cls, uuid: Union[str, UUID], text: str, fragment: Optional[str] = None
    ):
        """
        Convenience method to create valid resource_link ShortcodeTag objects.

        Args:
            - uuid: UUID or str object. If str, should either be coercable to
                uuid or 'sitemetadata'.
        """  # noqa: D401
        cls.validate_uuid(uuid)
        params = [ShortcodeParam(str(uuid)), ShortcodeParam(text)]
        if fragment:
            params.append(ShortcodeParam("#" + fragment))

        return cls(
            name="resource_link",
            percent_delimiters=True,
            params=params,
        )

    @classmethod
    def resource(
        cls,
        uuid: Union[str, UUID],
        href_uuid: Optional[Union[str, UUID]] = None,
        href: Optional[str] = None,
    ):
        """Convenience method to create valid resource_link ShortcodeTag objects."""  # noqa: D401
        cls.validate_uuid(uuid)
        params = [ShortcodeParam(name="uuid", value=str(uuid))]
        if href_uuid and href:
            msg = "At most one of href, href_uuid may be specified."
            raise ValueError(msg)
        if href_uuid:
            cls.validate_uuid(href_uuid)
            params.append(ShortcodeParam(name="href_uuid", value=str(href_uuid)))
        if href:
            params.append(ShortcodeParam(name="href", value=href))

        return cls(name="resource", percent_delimiters=False, params=params)

    @staticmethod
    def validate_uuid(uuid: Union[str, UUID]) -> None:
        if isinstance(uuid, UUID) or main.utils.is_valid_uuid(uuid):
            return
        msg = "Badly formed uuid."
        raise ValueError(msg)

    def get(self, param_name: Union[str, int], default: Optional[str] = None):
        """
        Retrieve a shortcode parameter value by name or position, providing
        `default` if param does not exist.
        """
        if isinstance(param_name, int):
            try:
                return self.params[param_name].value
            except IndexError:
                return default

        try:
            return next(p.value for p in self.params if p.name == param_name)
        except StopIteration:
            return default
