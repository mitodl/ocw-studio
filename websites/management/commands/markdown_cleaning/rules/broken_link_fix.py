import dataclasses
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
from urllib.parse import ParseResult, urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
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
    A Mixin to use with BrokenMarkdownLinkFixRule and BrokenMetadataLinkFixRule.

    This mixin holds the common broken link detection and replacement methods.

    The following types of links are detected as broken with some examples:

    1. Unnecessarily `_index` postfixed.
        Broken:
            - /courses/course-id/pages/page/_index
            - pages/page/_index
        Fixed (in markdown we use resource_link shortcode):
            - /courses/course-id/pages/page
            - pages/page
    2. Legacy URLs.
        Broken:
            - /courses/course-id/pages/section/subsection/content
            - pages/section/subsection/content
        Fixed (in markdown we use resource_link shortcode):
            - /courses/course-id/pages/content
            - pages/content
    3. Broken relative links. These appear under non-root pages, so these
       should be root-relative.
        Broken:
            - pages/page2
        Fixed (in markdown we use resource_link shortcode):
            - /pages/page2
    """

    Parser = partial(LinkParser, recursive=True)

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
        self,
        s: str,  # noqa: ARG002
        l: int,  # noqa: E741, ARG002
        toks: LinkParseResult,
        website_content,
    ):
        """
        Run on each match of the parser. The match will be replaced by the
        return value of this function.

        For more, see the docs for PyparsingRule.replace_match.
        """
        Notes = partial(
            self.ReplacementNotes, issue_type=None, linked_content=None, fix=None
        )

        try:
            url = urlparse(toks.link.destination)
        except ValueError:
            return toks.original_text, Notes(issue_type="Invalid URL")

        if url.scheme.startswith(("http", "ftp", "mailto")):
            # Fixing these is not in our scope, yet.
            return toks.original_text, Notes(issue_type="External URL")

        return self._find_content_and_replacement(toks, website_content, url)

    def should_parse(self, text: str) -> bool:
        """Return true if text has a markdown link."""
        return "](" in text

    @abstractmethod
    def create_replacement(
        self, result: LinkParseResult, url: ParseResult, wc: WebsiteContent
    ) -> (str, str):
        """
        Return a link for `wc` to use as a replacement for the broken link.

        Raises:
            NotImplementedError: When not implemented.
        """
        raise NotImplementedError

    def _find_best_matching_content(
        self, url: ParseResult, wc: WebsiteContent
    ) -> WebsiteContent | None:
        """
        Use the last segment of the url path to find a matching
        content in any of the content folders/paths.

        Returns None when either nothing is found or multiple
        matches are found.

        For example, for a url `pages/library/videos/lecture-6-debugging`
        this method may find the following contents:

        - pages/lecture-6-debugging
        - resources/lecture-6-debugging
        - video_galleries/lecture-6-debugging
        - lists/lecture-6-debugging
        etc.

        The paths, in which we search for the content, are defined
        in the site's starter config.

        Returns:
            Optional[WebsiteContent]: The matching WebsiteContent.
        """
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

    def _find_content_and_replacement(
        self, result: LinkParseResult, wc: WebsiteContent, url: ParseResult
    ) -> (str, ReplacementNotes):
        """
        Find the content that best matches the `url` and return the
        replacement.
        """
        Notes = partial(
            self.ReplacementNotes, issue_type=None, linked_content=None, fix=None
        )

        url_path = url.path.rstrip("/") or "/"
        if not url_path.startswith(("/", "courses/", r"{{< baseurl >}}")):
            # Most likely a relative URL like "pages/syllabus".
            # We'll make it root-relative to help with locating content.
            url_path = f"{get_rootrelative_url_from_content(wc)}/{url_path}"
        elif url_path.startswith("/") and not url_path.startswith("/courses"):
            # Probably a URL like "/pages/syllabus".
            # We'll prepend the website.url_path to help with the content
            # lookup.
            url_path = f"/{wc.website.url_path}{url_path}"

        try:
            found_wc = self.content_lookup.find(url_path, base_site=wc.website)
        except KeyError:
            found_wc = None

        replacement, notes = result.original_text, Notes()

        if found_wc and url_path.endswith(("_index", "index.htm", "index.html")):
            # Remove the extra _index* url component.
            # Example url_path: courses/id/pages/page/_index
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
                    issue_type="Unknown link: Unique fuzzy match",
                    fix=fix_note,
                    linked_content=found_wc.text_id,
                )

        return replacement, notes


class BrokenMarkdownLinkFixRule(BrokenLinkFixRuleMixin, PyparsingRule):
    """
    A rule to fix broken links in markdown.

    This rule replaces broken links with shortcodes (i.e. resource_link or resource).

    For information about the types of links replaced, see BrokenLinkFixRuleMixin.
    """

    alias = "broken_markdown_link_fix"

    fields = [
        "markdown",
    ]

    def create_replacement(
        self, result: LinkParseResult, url: ParseResult, wc: WebsiteContent
    ) -> (str, str):
        """
        Return a shortcode replacement text for `wc`.

        Returns:
            tuple(str, str): The shortcode text and note/comment.
        """
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
    A rule to fix broken links in metadata.

    This rule replaces broken links with markdown links.

    For information about the types of links replaced, see BrokenLinkFixRuleMixin.
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
    ) -> (str, str):
        """
        Return a markdown link replacement text for `wc`.

        Returns:
            tuple(str, str): The shortcode text and note/comment.
        """
        content_url = get_rootrelative_url_from_content(wc)

        fragment = f"#{url.fragment}" if url.fragment else ""
        new_link = dataclasses.replace(
            result.link, destination=f"{content_url}{fragment}"
        )

        return new_link.to_markdown(), "Replaced with rootrelative URL"
