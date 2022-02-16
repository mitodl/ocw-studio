import abc
from re import Match

from websites.models import WebsiteContent


class MarkdownCleanupRule(abc.ABC):
    """
    Abstract base class for markdown cleanup rules to be registered with
    MarkdownCleanup management command.
    """

    @property
    @abc.abstractclassmethod
    def alias(cls) -> str:
        """Alias of the rule to be used in CLI"""

    @property
    @abc.abstractclassmethod
    def regex(cls) -> str:
        """
        The pattern to match for when making replacements.
        """

    @abc.abstractmethod
    def __call__(self, match: Match, website_cosntent: WebsiteContent):
        """
        Invoked for each match to the rule's regex and returns the replacement
        string. Similar to re.sub, but invoked with website_content argument
        also.
        """
