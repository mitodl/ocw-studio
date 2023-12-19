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
)
from websites.models import WebsiteContent


class BrokenLinkFixRule(PyparsingRule):
    """
    Fix links.
    """

    alias = "broken_link_fix"

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

    @dataclass
    class ReplacementNotes:
        fixed: str | None

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()
        self.config_lookup = StarterSiteConfigLookup()

    def replace_match(
        self, s: str, l: int, toks, website_content  # noqa: ARG002, E741
    ):
        return self.find_replacement(toks, website_content)

    def should_parse(self, text: str):
        """Should the text be parsed?

        If the text does not contain '](', then it definitely does not have
        markdown links.
        """  # noqa: D401
        return "](" in text

    def create_replacement(
        self, result: LinkParseResult, url: ParseResult, wc: WebsiteContent
    ) -> (str, ReplacementNotes):
        try:
            if result.link.is_image:
                sc = ShortcodeTag.resource(wc.text_id)
            else:
                sc = ShortcodeTag.resource_link(
                    wc.text_id, result.link.text, url.fragment
                )
            return sc.to_hugo(), self.ReplacementNotes(fixed="found wc")
        except:  # noqa: E722
            return result.original_text, self.ReplacementNotes(fixed="error")

    def _find_best_matching_content(self, url: ParseResult, wc: WebsiteContent):
        filename = url.path.rstrip("/").split("/")[-1]

        config = self.config_lookup.get_config(wc.website.starter_id)
        for item in config.iter_items():
            if item.is_folder_item():
                dirpath = item.item.get("folder", "").replace(config.content_dir, "", 1)
                try:
                    return self.content_lookup.find_within_site(
                        wc.website_id, f"{dirpath}/{filename}"
                    )
                except KeyError:
                    pass
        return None

    def find_replacement(  # noqa: PLR0911
        self, result: LinkParseResult, wc: WebsiteContent
    ):
        link = result.link
        Notes = partial(self.ReplacementNotes, fixed=None)

        try:
            url = urlparse(link.destination)
        except ValueError:
            return result.original_text, Notes(fixed="invalid url")

        if url.scheme.startswith(("http", "ftp", "mailto")):
            return result.original_text, Notes(fixed="skipped")

        try:
            website_by_path = self.content_lookup.find_website_by_url_path(url.path)
        except KeyError:
            website_by_path = None

        if (
            url.path.startswith(("courses", "/courses"))
            and website_by_path is not None
            and website_by_path.unpublish_status is None
        ):
            link.destination = "/" + link.destination
            return link.to_markdown(), Notes(fixed="absolute course url")

        url_path = url.path.rstrip("/") or "/"

        try:
            found_wc = self.content_lookup.find(url_path, base_site=wc.website)
            found_in_same_site = found_wc.website_id == wc.website_id
        except KeyError:
            found_wc = None
            found_in_same_site = False

        if (
            found_wc
            and found_in_same_site
            and url_path.endswith(("index.htm", "index.html", "_index"))
        ):
            return self.create_replacement(result, url, found_wc)

        if found_wc:
            return result.original_text, Notes(fixed="nothing to do")

        found_wc = self._find_best_matching_content(url, wc)

        if found_wc:
            return self.create_replacement(result, url, found_wc)

        return result.original_text, Notes(fixed="no match")
