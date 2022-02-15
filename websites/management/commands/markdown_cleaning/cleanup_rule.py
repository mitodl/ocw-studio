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
        """Name of the rule"""

    @property
    @abc.abstractclassmethod
    def regex(cls) -> str:
        """Name of the rule"""

    @abc.abstractmethod
    def __call__(self, match: Match, website_cosntent: WebsiteContent):
        pass
