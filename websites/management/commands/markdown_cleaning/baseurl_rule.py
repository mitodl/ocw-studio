"""Replace baseurl-based links with resource_link shortcodes."""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import ContentLookup
from websites.models import WebsiteContent


class BaseurlReplacementRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner. Replaces
    baseurl links with % resource_link % shortcodes.

    This is intentially limited in scope for now. Some baseurl links, such as
    those whose titles are images or include square brackets, are excluded from
    replacement.
    """

    regex = (
        r"\\?\[(?P<title>[^\[\]\n]*?)\\?\]"
        + r"\({{< baseurl >}}(?P<url>.*?)"
        + r"(/?(?P<fragment>#.*?))?"
        + r"\)"
    )

    alias = "baseurl"

    def __init__(self):
        self.content_lookup = ContentLookup()

    def __call__(self, match: re.Match, website_content: WebsiteContent):
        original_text = match[0]
        escaped_title = match.group("title").replace('"', '\\"')
        url = match.group("url")
        fragment = match.group("fragment")

        # This is probably a link with image as title, where the image is a < resource >
        if R"{{<" in match.group("title"):
            return original_text

        try:
            linked_content = self.content_lookup.find(website_content.website_id, url)
            fragment_arg = f' "{fragment}"' if fragment is not None else ""
            return f'{{{{% resource_link {linked_content.text_id} "{escaped_title}"{fragment_arg} %}}}}'
        except KeyError:
            return original_text
