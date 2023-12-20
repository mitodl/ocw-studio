from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
from urllib.parse import ParseResult, urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
    MarkdownLink,
)
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.management.commands.markdown_cleaning.utils import (
    ContentLookup,
    StarterSiteConfigLookup,
    get_rootrelative_url_from_content,
)
from websites.models import WebsiteContent


class BrokenLinkFixRuleMixin(ABC):
    """
    Fix links.
    """

    alias = "broken_link_fix"

    Parser = partial(LinkParser, recursive=True)

    fields = []

    @dataclass
    class ReplacementNotes:
        issue_type: str | None
        fix: str | None
        linked_content: WebsiteContent | None

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()
        self.config_lookup = StarterSiteConfigLookup()

    def replace_match(
        self, s: str, l: int, toks, website_content  # noqa: ARG002, E741
    ):
        return self.find_replacement(toks, website_content)

    def should_parse(self, text: str):
        """Return true if text has a markdown link."""
        return "](" in text

    @abstractmethod
    def create_replacement(
        self, result: LinkParseResult, url: ParseResult, wc: WebsiteContent
    ) -> (str, str):
        raise NotImplementedError

    def _find_best_matching_content(self, url: ParseResult, wc: WebsiteContent):
        filename = url.path.rstrip("/").split("/")[-1]

        config = self.config_lookup.get_config(wc.website.starter_id)
        matched_contents = []

        for item in self.config_lookup.config_items(wc.website.starter_id):
            if item.is_folder_item():
                dirpath = item.item.get("folder", "").replace(config.content_dir, "", 1)
                try:
                    content = self.content_lookup.find_within_site(
                        wc.website_id, f"{dirpath}/{filename}"
                    )
                    if content:
                        matched_contents.append(content)
                except KeyError:
                    pass
        if len(matched_contents) == 1:
            return matched_contents[0]

        return None

    def find_replacement(  # noqa: C901,PLR0912
        self, result: LinkParseResult, wc: WebsiteContent
    ):
        link = result.link
        Notes = partial(
            self.ReplacementNotes, issue_type=None, linked_content=None, fix=None
        )

        try:
            url = urlparse(link.destination)
        except ValueError:
            return result.original_text, Notes(issue_type="Invalid URL")

        if url.scheme.startswith(("http", "ftp", "mailto")):
            # Fixing these is not in our scope, yet.
            return result.original_text, Notes(issue_type="External URL")

        if url.path.startswith("courses/"):
            try:
                website_by_path = self.content_lookup.find_website_by_url_path(url.path)
            except KeyError:
                website_by_path = None

            if website_by_path and website_by_path.unpublish_status is None:
                # This is a course URL.
                # These need to be absolute URLs to work correctly.
                link.destination = "/" + link.destination
                return link.to_markdown(), Notes(
                    issue_type="Relative course URL",
                    fix="Make URL Absolute",
                    linked_content=website_by_path.name,
                )

        url_path = url.path.rstrip("/") or "/"
        if not url_path.startswith("/"):
            # Most likely a relative URL like "pages/syllabus".
            # We'll make it root-relative.
            url_path = f"{get_rootrelative_url_from_content(wc)}/{url_path}"

        try:
            found_wc = self.content_lookup.find(url_path, base_site=wc.website)
        except KeyError:
            found_wc = None

        replacement, notes = result.original_text, Notes()

        if found_wc and url_path.endswith(("_index", "index.htm", "index.html")):
            # Remove the extra _index* url component.
            replacement, fix_note = self.create_replacement(result, url, found_wc)
            notes = Notes(
                issue_type="_index postfix",
                fix=fix_note,
                linked_content=found_wc.text_id,
            )
        elif found_wc:
            # A WebsiteContent was successfully discovered. We probably don't
            # need to do anything.
            replacement, notes = result.original_text, Notes(issue_type="Nothing to do")
        else:
            # Start making guesses.
            found_wc = self._find_best_matching_content(url, wc)
            notes = Notes(issue_type="Unknown link")

            if found_wc:
                replacement, fix_note = self.create_replacement(result, url, found_wc)
                notes = Notes(
                    issue_type="Unknown link",
                    fix=fix_note,
                    linked_content=found_wc.text_id,
                )

        return replacement, notes


class BrokenMarkdownLinkFixRule(BrokenLinkFixRuleMixin, PyparsingRule):
    """
    Fix links.
    """

    alias = "broken_markdown_link_fix"

    fields = [
        "markdown",
    ]

    def create_replacement(
        self, result: LinkParseResult, url: ParseResult, wc: WebsiteContent
    ) -> (str, str):
        try:
            if result.link.is_image:
                sc = ShortcodeTag.resource(wc.text_id)
            else:
                sc = ShortcodeTag.resource_link(
                    wc.text_id, result.link.text, url.fragment
                )
            return sc.to_hugo(), "Replaced with shortcode"
        except:  # noqa: E722
            return result.original_text, ""


class BrokenMetadataLinkFixRule(BrokenLinkFixRuleMixin, PyparsingRule):
    """
    Fix links.
    """

    alias = "broken_metadata_link_fix"

    fields = [
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    def create_replacement(
        self, result: LinkParseResult, url: ParseResult, wc: WebsiteContent
    ) -> (str, BrokenLinkFixRuleMixin.ReplacementNotes):
        content_url = get_rootrelative_url_from_content(wc)
        link = result.link
        fragment = f"#{url.fragment}" if url.fragment else ""

        new_link = MarkdownLink(
            text=link.text,
            destination=f"{content_url}{fragment}",
            is_image=link.is_image,
            title=link.title,
        )

        return new_link.to_markdown(), "Replaced with rootrelative URL"
