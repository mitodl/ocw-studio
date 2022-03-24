import abc
import re
from dataclasses import dataclass
from typing import Union

from pyparsing import ParseResults

from websites.management.commands.markdown_cleaning.parsing_utils import WrappedParser
from websites.models import WebsiteContent


class MarkdownCleanupRule(abc.ABC):
    """
    Abstract base class for markdown cleanup rules to be registered with
    MarkdownCleanup management command.

    Rules should be used with WebsiteContentMarkdownCleaner. For regex-based
    rules, inherit from RegexpCleanupRule.
    """

    @property
    @abc.abstractclassmethod
    def alias(cls) -> str:
        """Alias of the rule to be used in CLI"""

    @abc.abstractmethod
    def transform_text(
        self, website_content: WebsiteContent, text: str, on_match
    ) -> str:
        """Transform markdown associated with a website_content object.

        Calls on_match(original_text, replacement, website_content, replacement_notes) for
        each match.
        """

    @dataclass
    class ReplacementNotes:
        """Used to store notes about this replacement, e.g., the values of named
        regex capturing groups.
        """

    fields = ["markdown"]

    @classmethod
    def get_root_fields(cls):
        return {f.split(".")[0] for f in cls.fields}

    @classmethod
    def standardize_replacement(cls, result: Union[str, tuple]):
        if isinstance(result, str):
            replacement = result
            notes = cls.ReplacementNotes()
        elif isinstance(result, tuple):
            replacement, notes = result
        else:
            raise ValueError("replace_match must return strings or tuples when called")
        return replacement, notes


class RegexpCleanupRule(MarkdownCleanupRule):
    """
    Regex-based replacements on markdown.
    """

    @property
    @abc.abstractclassmethod
    def regex(cls) -> str:
        """
        The pattern to match for when making replacements.
        """

    def __init__(self) -> None:
        self.compiled = re.compile(self.regex)

    @abc.abstractmethod
    def replace_match(self, match: re.Match, website_content: WebsiteContent):
        """
        Invoked for each match to the rule's regex and returns the replacement
        string. Similar to re.sub, but invoked with website_content argument
        also.
        """

    def transform_text(
        self, website_content: WebsiteContent, text: str, on_match
    ) -> str:
        def _replacer(match: re.Match):
            result = self.replace_match(match, website_content)
            replacement, notes = self.standardize_replacement(result)

            original_text = match[0]
            on_match(original_text, replacement, website_content, notes)

            return replacement

        new_markdown = self.compiled.sub(_replacer, text)
        return new_markdown


class PyparsingRule(MarkdownCleanupRule):
    @property
    @abc.abstractclassmethod
    def Parser(cls) -> WrappedParser:
        """Parser for this rule"""

    @abc.abstractmethod
    def replace_match(
        self, s: str, l: int, toks: ParseResults, website_content: WebsiteContent
    ):
        pass

    def __init__(self) -> None:
        super().__init__()
        self.parser = self.Parser()

    def should_parse(self, _text: str):
        """
        Determines whether a given text (e.g., markdown page) should be parsed
        at all. If result is truthy, the text will be parsed.

        This is an optional optimization mechanism. If we are going to parse a
        text, we need to parse it all, and Pyparsing is not particularly fast.
        So a text can be easily and quickly ruled out as having no relevant
        content WITHOUT parsing the text, put that logic here.

        Example:
        =======
        If using ShortcodeParser to make edits to {{ < resource > }} shortcodes,
        don't bother parsing pages that don't contain the string '{{ < resource'

        N.B: If the page is parsed, all parse matches will be included in the
        generated CSV. Continuing with the {{< resource > }} shortcode example,
        if a page contains '{{< resource ', then ALL shortcodes within that page
        will be parsed whether they are resource shortcodes or some other
        shortcode.
        """
        return True

    def transform_text(
        self, website_content: WebsiteContent, text: str, on_match
    ) -> str:
        if not self.should_parse(text):
            return text

        def parse_action(s, l, toks):
            result = self.replace_match(s, l, toks, website_content)
            replacement, notes = self.standardize_replacement(result)
            original_text = toks.original_text
            on_match(original_text, replacement, website_content, notes)
            return replacement

        self.parser.set_parse_action(parse_action)

        return self.parser.transform_string(text)
