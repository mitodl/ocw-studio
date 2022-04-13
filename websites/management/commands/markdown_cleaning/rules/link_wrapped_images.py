"""Replace link-wrapped images with resource shortcodes"""
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from pyparsing import ParseException

import main.utils
from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
    MarkdownLink,
)
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParser,
    ShortcodeParseResult,
    ShortcodeTag,
)
from websites.management.commands.markdown_cleaning.utils import (
    ContentLookup,
    get_rootrelative_url_from_content,
)
from websites.models import WebsiteContent


class LinkWrappedImagesRule(PyparsingRule):
    """
    Turn link-wrapped images into resource shortcodes with href/href_uuid params

    Example
    =======

    Original text:
        Hello [{{< resource some_uuid >}}extra text](url) World
    Becomes
        Hello {{< resource uuid="some_uuid" href_uuid="url_uuid" >}}{{< resource_link "url_uuid" "extra text" >}}
    or
        Hello {{< resource uuid="some_uuid" href="url" >}}[extra text](url)

    depending on whether the url is within-course or not.
    """

    alias = "link_wrapped_images"

    Parser = LinkParser

    @dataclass
    class ReplacementNotes:
        note: str
        had_extra_text: Optional[bool] = None

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

        # Use a separate parser for images inside link text... we don't want
        # to fire parse actions attached to self.parser in that case.
        self.shortcode_parser = ShortcodeParser()

    def should_parse(self, text: str):
        return "[{{< resource" in text

    def replace_match(self, s, l, toks: LinkParseResult, wc: WebsiteContent):
        """
        Replace a single markdown link with shortcodes.

        If this link is not a link-wrapped resource, ignore it. If it is,
        update the shortcode to use href/href_uuid params. Possibly add a
        resource_link shortcode to account for other text in the link.
        """
        Notes = self.ReplacementNotes
        link = toks.link
        text = link.text.strip()
        fragment = urlparse(link.destination).fragment
        if "{{< resource" not in text:
            return toks.original_text, Notes("No resource shortcode in link text.")
        if text.count("{{<") > 1:
            # There are only three of these; deal with them by hand.
            return toks.original_text, Notes("Multiple shortcodes in link text.")

        try:
            regexp = re.compile(r"(?P<shortcode>\{\{<.*?>\}\})(?P<extra_text>.*)")
            match = regexp.match(text)
            if not match:
                return toks.original_text, Notes("Unexpected: No regex match.")
            parsed: ShortcodeParseResult = self.shortcode_parser.parse_string(
                match.group("shortcode")
            )
            extra_text = match.group("extra_text")
        except ParseException:
            return toks.original_text, Notes("Unexpected: Shortcode parsing error")

        if parsed.shortcode.name != "resource":
            return toks.original_text, Notes("Unexpected: Not a resource shortcode")

        resource = parsed.shortcode
        if len(resource.params) != 1:
            return toks.original_text, Notes(
                f"Unexpected: wrong number of shortcode parameters: {len(resource.params)}"
            )
        resource_uuid = resource.get(0)

        try:
            linked_content = self.content_lookup.find(
                link.destination, base_site=wc.website
            )
        except KeyError:
            new_resource = ShortcodeTag.resource(
                uuid=resource_uuid, href=link.destination
            )
            new_extra = (
                ""
                if not extra_text
                else MarkdownLink(
                    text=extra_text, destination=link.destination
                ).to_markdown()
            )
            replacement = new_resource.to_hugo() + new_extra
            return replacement, Notes(
                "href---link is not to Websitecontent", had_extra_text=bool(extra_text)
            )

        return self.get_replacement(
            page_content=wc,
            linked_content=linked_content,
            resource_uuid=resource_uuid,
            extra_text=extra_text,
            fragment=fragment,
        )

    def get_replacement(
        self,
        page_content: WebsiteContent,
        linked_content: WebsiteContent,
        resource_uuid: str,
        extra_text: str,
        fragment: str,
    ):
        """
        Return new text for resource shortcode that was previously wrapped in
        a link linking to `linked_content`.

        The link was originally of the form:
            [{{< resource resource_uuid >}}maybe_extra_text](destination)
        where `destination` points to `linked_content`, possibly with a fragment.

        The replacement text will be:
        {{< resource uuid="..." href="..." OR href_uuid="..." >}}
        possibly followed by
            {{% resource_link "uuid" "extra text originally after resource" %}} OR
            [extra text origianlly after resource](destination)
        if there was extra text inside the original link.
        """
        Notes = self.ReplacementNotes

        rootrel_url = get_rootrelative_url_from_content(linked_content)
        if fragment:
            rootrel_url += "#" + fragment

        can_link_with_uuid = (
            linked_content.website.name == page_content.website.name
            and main.utils.is_valid_uuid(linked_content.text_id)
        )

        if can_link_with_uuid:
            new_resource = ShortcodeTag.resource(
                uuid=resource_uuid, href_uuid=linked_content.text_id
            )
            new_extra = (
                ""
                if not extra_text
                else ShortcodeTag.resource_link(
                    uuid=linked_content.text_id, text=extra_text, fragment=fragment
                ).to_hugo()
            )

            replacement = new_resource.to_hugo() + new_extra
            return replacement, Notes(
                "href_uuid (within-site, not to sitemetadata)",
                had_extra_text=bool(extra_text),
            )
        else:
            new_resource = ShortcodeTag.resource(uuid=resource_uuid, href=rootrel_url)
            new_extra = (
                ""
                if not extra_text
                else MarkdownLink(
                    text=extra_text, destination=rootrel_url
                ).to_markdown()
            )
            replacement = new_resource.to_hugo() + new_extra
            return replacement, Notes(
                "href (cross-site or to sitemetadata)", had_extra_text=bool(extra_text)
            )
