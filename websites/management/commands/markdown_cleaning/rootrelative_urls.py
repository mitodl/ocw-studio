"""
WebsiteContentMarkdownCleaner rule to convert root-relative urls to resource_links
"""
import re

from websites.models import WebsiteContent
from websites.management.commands.markdown_cleaning.utils import (
    UrlSiteRelativiser
)
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)

class RootRelativeUrlRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner."""

    regex = (
        r"(?P<image_prefix>!?)"             # optional leading "!" to determine if it's a link or an image
        + r"\\?\["                          # match title opening "[" (or "\[" in case corrupted by studio save)
        + r"(?P<title>[^\[\]\<\>\n]*?)"     # capture the title
        + r"\\?\]"                          # title closing "]" (or "\]")
        + r"\("                             # url open
        + r"/?"                             # optional, non-captured leading "/"
        + r"(?P<url>(course|resource).*?)"  # capture the url, but only if it's course/ or resoruce/... we don't want links to wikipedia.
        + r"\)"                             # url close
    )

    alias = "rootrelative_urls"

    def __init__(self) -> None:
        self.get_site_relative_url = UrlSiteRelativiser()

    def __call__(self, match: re.Match, website_content: WebsiteContent) -> str:
        original_text = match[0]
        url = match.group('url')
        try:
            return str(self.get_site_relative_url(url)[1])
        except StopIteration:
            return original_text

