import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.models import WebsiteContent


class OCWNextReplacement(RegexpCleanupRule):
    """
    Convert ocwnext urls to root-relative.

    We'll make them shortcodes or something later.
    """

    regex = r"https://ocwnext\.odl\.mit\.edu/"

    alias = "ocwnext"

    fields = [
        "markdown",
        "metadata.description",
    ]

    def replace_match(self, match: re.Match, website_content: WebsiteContent):
        return "/"
