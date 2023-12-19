import re
import uuid
from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
)
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.models import Website, WebsiteContent


class LinkResolveuidRule(PyparsingRule):
    """
    Rule to fix resolveuid links.
    """

    alias = "link_resolveuid"

    Parser = partial(LinkParser, recursive=True)

    fields = [
        "markdown",
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    __link_markdown_pattern = re.compile(r"\]\(.*resolveuid.*\)")
    __link_pattern = re.compile(r".*resolveuid/(.*)")

    @dataclass
    class ReplacementNotes:
        is_resolveuid_link: bool
        found_referenced_entity: bool
        text_id: str

    def _find_link_replacement(
        self, text_id: str, result: LinkParseResult, website: Website
    ) -> str | None:
        """
        Find content corresponding to `text_id` or `result` and return a valid
        replacement.
        """
        text = result.link.text

        # text_id matches a content in the same website.
        if WebsiteContent.objects.filter(text_id=text_id, website=website).exists():
            return ShortcodeTag.resource_link(text_id, text).to_hugo()

        # text matches a content's title
        contents = WebsiteContent.objects.filter(title=text, website=website)
        if contents.count() == 1:
            content = contents.first()
            return ShortcodeTag.resource_link(
                content.text_id, text, urlparse(result.link.destination).fragment
            ).to_hugo()

        # text_id is a legacy site id
        websites = Website.objects.filter(
            metadata__legacy_uid=text_id, unpublish_status__isnull=True
        )
        if websites.count() == 1:
            website = websites.first()
            return f'[{text}](/{website.url_path.lstrip("/")})'

        return None

    def _uuid(self, text: str) -> uuid.UUID | None:
        """Return UUID if `text` is a valid UUID."""
        try:
            return uuid.UUID(text)
        except ValueError:
            return None

    def replace_match(
        self, s: str, l: int, toks, website_content  # noqa: ARG002, E741
    ):
        """
        Replace resolveuid links with resource_links or markdown links, if applicable.
        """
        link_match = self.__link_pattern.match(toks[0].destination)

        is_resolveuid_link = link_match is not None
        replacement_text = toks.original_text
        text_id = None  # content text_id

        notes = self.ReplacementNotes(
            is_resolveuid_link=is_resolveuid_link,
            found_referenced_entity=False,
            text_id=text_id,
        )

        if not is_resolveuid_link:
            return replacement_text, notes

        text_id = str(self._uuid(link_match.group(1).lower()))

        if text_id is not None:
            notes.text_id = text_id
            replacement = self._find_link_replacement(
                text_id, toks, website=website_content.website
            )

            if replacement is not None:
                notes.found_referenced_entity = True
                replacement_text = replacement

        return replacement_text, notes

    def should_parse(self, text: str) -> bool:
        """
        Return true if the content might contain a resolveuid link.
        """
        return self.__link_markdown_pattern.search(text) is not None
