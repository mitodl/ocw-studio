import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.models import WebsiteContent


class RelatedResourcesTextRule(RegexpCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner."""

    regex = (
          r"\\?\["  # match title opening "[" (or "\[" in case corrupted by studio save)
        + r"(?P<title>[^\[\]\<\>\n]*?)"  # capture the title
        + r"\\?\]"  # title closing "]" (or "\]")
        + r"\("  # url open
        + r"(?P<url>(resources).*?)"  # capture the url, but only if it's course/ or resoruce/... we don't want links to wikipedia.
        + r"\)"  # url close
    )

    alias = "related_resources_text"

    field = 'metadata'
    subfield = "related_resources_text"

    def replace_match(self, match: re.Match, website_content: WebsiteContent):
        return match[0]
