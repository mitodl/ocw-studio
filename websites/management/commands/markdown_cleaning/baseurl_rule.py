"""Replace baseurl-based links with resource_link shortcodes."""
import re
from urllib.parse import urlparse
from dataclasses import dataclass

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    PyparsingRule,
)
from websites.management.commands.markdown_cleaning.parsing_utils import (
    ShortcodeTag,
)
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult
)
from websites.management.commands.markdown_cleaning.utils import ContentLookup
from websites.models import WebsiteContent


class BaseurlReplacementRule(PyparsingRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner. Replaces
    baseurl links with % resource_link % shortcodes.

    This is intentially limited in scope for now. Some baseurl links, such as
    those whose titles are images or include square brackets, are excluded from
    replacement.
    """

    Parser = LinkParser

    alias = "baseurl"
    @dataclass
    class ReplacementNotes:
        wraps_image: bool = False

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()
    
    def should_parse(self, text: str):
        return 'baseurl' in text

    def replace_match(self, s, l, toks: LinkParseResult, website_content: WebsiteContent):
        Notes = self.ReplacementNotes
        original_text = toks.original_text
        link = toks.link

        dest_match = re.search(r'\{\{< baseurl >\}\}(?P<dest>.*)', link.destination)
        if dest_match is None:
            return original_text
        url = urlparse(dest_match.group('dest'))

        # This is probably a link with image as title, where the image is a < resource >
        if R"{{<" in link.text or link.text_links:
            return original_text, Notes(wraps_image=True)
        try:
            linked_content = self.content_lookup.find_within_site(
                website_content.website_id, url.path
            )
            if link.is_image:
                # This shouldn't really happy. ocw-to-hugo converted images
                # to resource shortcodes but not links to resource_links.
                shortcode = ShortcodeTag.resource(linked_content.text_id)
            else:
                shortcode = ShortcodeTag.resource_link(
                    uuid=linked_content.text_id,
                    text=link.text,
                    fragment=url.fragment
                )
            return shortcode.to_hugo()
        except KeyError:
            return original_text
