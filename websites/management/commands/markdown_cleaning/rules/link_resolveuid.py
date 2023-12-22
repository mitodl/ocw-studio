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
from websites.management.commands.markdown_cleaning.utils import ContentLookup
from websites.models import Website, WebsiteContent


class LinkResolveuidRule(PyparsingRule):
    """
    Rule to fix resolveuid links by replacing them with shortcodes.

    Example:
        - ./resolveuid/89ce47d27edcdd9b8a8cbe641a59b520

    The fix attempts the following:

    1. Find content matching the UUID in the link.
    2. Find a course with a matching legacy UUID.
    3. Find a unique content matching the link text.
    """

    alias = "link_resolveuid"

    Parser = partial(LinkParser, recursive=True)

    fields = [
        "markdown",
    ]

    __link_markdown_pattern = re.compile(r"\]\(.*resolveuid.*\)")
    __link_pattern = re.compile(r".*resolveuid/(.*)")

    @dataclass
    class ReplacementNotes:
        is_resolveuid_link: bool
        found_referenced_entity: bool
        text_id: str | None
        match_type: str | None

    def __init__(self) -> None:
        super().__init__()

        self.content_lookup = ContentLookup()

    def _find_link_replacement(
        self, text_id: uuid.UUID, result: LinkParseResult, website: Website
    ) -> (str | None, ReplacementNotes):
        """
        Find content corresponding to `text_id` or `result.link.text`
        and return a valid replacement.
        """
        text = result.link.text
        Notes = partial(
            self.ReplacementNotes,
            is_resolveuid_link=True,
            found_referenced_entity=True,
            text_id=None,
            match_type=None,
        )

        try:
            content = self.content_lookup.find_by_uuid(text_id)
        except KeyError:
            content = None

        # text_id matches a content in the same website.
        if content and content.website == website:
            return ShortcodeTag.resource_link(str(text_id), text).to_hugo(), Notes(
                text_id=str(text_id), match_type="text_id"
            )

        # text_id is a legacy site id
        websites = Website.objects.filter(
            metadata__legacy_uid=str(text_id), unpublish_status__isnull=True
        )
        if websites.count() == 1:
            website = websites.first()
            return f'[{text}](/{website.url_path.lstrip("/")})', Notes(
                match_type="legacy website uid"
            )

        # text matches a content's title
        contents = WebsiteContent.objects.filter(title=text, website=website)
        if contents.count() == 1:
            content = contents.first()
            return ShortcodeTag.resource_link(
                content.text_id, text, urlparse(result.link.destination).fragment
            ).to_hugo(), Notes(match_type="content title")

        return None, Notes(found_referenced_entity=False)

    def _uuid(self, text: str) -> uuid.UUID | None:
        """Return UUID if `text` is a valid UUID."""
        try:
            return uuid.UUID(text)
        except ValueError:
            return None

    def replace_match(
        self, s: str, l: int, toks, website_content  # noqa: E741, ARG002
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
            match_type=None,
            text_id=None,  # replaced content text_id
        )

        if not is_resolveuid_link:
            return replacement_text, notes

        text_id = self._uuid(link_match.group(1).lower())

        if text_id is not None:
            replacement, notes = self._find_link_replacement(
                text_id, toks, website=website_content.website
            )

            if replacement is not None:
                replacement_text = replacement

        return replacement_text, notes

    def should_parse(self, text: str) -> bool:
        """
        Return true if the `text` contains a resolveuid link.
        """
        return self.__link_markdown_pattern.search(text) is not None
