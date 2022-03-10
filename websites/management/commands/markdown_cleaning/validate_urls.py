import re
from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import ContentLookup
from websites.models import WebsiteContent


class ValidateUrls(RegexpCleanupRule):
    """
    This rule never changes anything. Its intent is to find links and validate
    that they work.
    """

    regex = (
        # Do not try to capture link text, else we'll miss images inside links
        # because the regex matches will overlap
        r"\\?\]"  # title closing "]" (or "\]")
        + r"\("  # url open
        + r"(?P<url>[^\s]*?)"  # capture the url
        + r"(\s\"(?P<title>.*?)\")?"  # capture optional title
        + r"\)"  # url close
    )

    alias = "validate_urls"

    fields = [
        "markdown",
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    @dataclass
    class ReplacementNotes:
        link_type: str
        url_path: str
        links_to_course: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

    def replace_match(self, match: re.Match, wc: WebsiteContent):
        url = urlparse(match.group("url"))
        original_text = match[0]
        notes = partial(self.ReplacementNotes, url_path=url.path)

        if url.scheme.startswith("http"):
            return original_text, notes(link_type="global link")

        if not url.path.startswith("/courses"):
            return original_text, notes(link_type="not course link")

        try:
            linked_content = self.content_lookup.find(url.path)
            return original_text, notes(
                link_type="course link", links_to_course=linked_content.website.name
            )
        except KeyError:
            return original_text, notes(link_type="content not found")
