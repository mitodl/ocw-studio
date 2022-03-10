import abc
import re
from dataclasses import dataclass

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
            if isinstance(result, str):
                replacement = result
                notes = self.ReplacementNotes()
            elif isinstance(result, tuple):
                replacement, notes = result
            else:
                raise ValueError(
                    "replace_match must return strings or tuples when called"
                )

            original_text = match[0]
            on_match(original_text, replacement, website_content, notes)

            return replacement

        new_markdown = self.compiled.sub(_replacer, text)
        return new_markdown
