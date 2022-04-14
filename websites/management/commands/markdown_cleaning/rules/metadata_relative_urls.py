import re
from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import (
    ContentLookup,
    get_rootrelative_url_from_content,
)
from websites.models import WebsiteContent


class MetadataRelativeUrlsRule(RegexpCleanupRule):
    """
    Turn relative metadata links into root-relative links. :sob:

    These cannot turn into shortcodes because our metadata is rendered
    via RenderString, which does not support shortcodes.
    """

    regex = (
        r"\\?\["  # match title opening "[" (or "\[" in case corrupted by studio save)
        + r"(?P<text>[^\[\]\<\>\n]*?)"  # capture the title
        + r"\\?\]"  # title closing "]" (or "\]")
        + r"\("  # url open
        + r"(?P<url>[^\s]*?)"  # capture the url
        + r"(\s(?P<title>.*?))?"  # capture optional title
        + r"\)"  # url close
    )

    alias = "metadata_relative_urls"

    fields = [
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    @dataclass
    class ReplacementNotes:
        regex_text: str
        url_path: str
        regex_title: str
        replacement_type: str

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

    def replace_match(self, match: re.Match, website_content: WebsiteContent):
        regex_text = match.group("text")
        url = urlparse(match.group("url"))
        regex_title = match.group("title")
        original_text = match[0]
        notes = partial(
            self.ReplacementNotes,
            regex_text=regex_text,
            url_path=url.path,
            regex_title=regex_title,
        )

        if url.scheme.startswith("http"):
            return original_text, notes(replacement_type="global link")
        if url.path.startswith("/courses"):
            return original_text, notes(replacement_type="course link")

        content_relative_path = "/" + url.path.lstrip("/")

        try:
            linked_content = self.content_lookup.find_within_site(
                website_content.website_id, content_relative_path
            )
        except KeyError:
            return original_text, notes(replacement_type="content not found")

        link_url = get_rootrelative_url_from_content(linked_content)
        if url.fragment:
            link_url += f"#{url.fragment}"

        # The link titles are all "Open in a new window". And they won't open in
        # a new window. So just discard the title.
        replacement = f"[{regex_text}]({link_url})"
        return replacement, notes(replacement_type="converted")
