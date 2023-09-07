from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
)
from websites.management.commands.markdown_cleaning.utils import ContentLookup
from websites.models import WebsiteContent


class LinkLoggingRule(PyparsingRule):
    """
    Find all links in all Websitecontent markdown bodies plus some metadata
    fields and log information about them to a csv.

    Never changes stuff.
    """

    alias = "link_logging"

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
        link_type: str
        text: str
        destination: str
        title: str
        is_image: bool
        scheme: str
        broken_best_guess: str = "No"

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

    def replace_match(
        self, s: str, l: int, toks, website_content  # noqa: ARG002, E741
    ):
        return toks.original_text, self.classify_link(toks, website_content)

    def should_parse(self, text: str):
        """Should the text be parsed?

        If the text does not contain '](', then it definitely does not have
        markdown links.
        """  # noqa: D401
        return "](" in text

    def classify_link(  # noqa: C901, PLR0911, PLR0912
        self, result: LinkParseResult, wc: WebsiteContent
    ):  # noqa: PLR0911, PLR0912, RUF100
        link = result.link
        Notes = partial(
            self.ReplacementNotes,
            text=link.text,
            destination=link.destination,
            title=link.title,
            is_image=link.is_image,
        )
        try:
            url = urlparse(link.destination)
        except ValueError:
            return Notes(link_type="invalid url", scheme="")
        Notes = partial(Notes, scheme=url.scheme)

        skip_schemes_prefixes = ["http", "ftp", "mailto"]
        if any(url.scheme.startswith(p) for p in skip_schemes_prefixes):
            return Notes(link_type="global")

        if url.path.startswith("/courses"):
            try:
                self.content_lookup.find(url.path)
                return Notes(link_type="found course content")
            except KeyError:
                pass

        if url.path.startswith(R"{{< baseurl >}}"):
            try:
                self.content_lookup.find(url.path, base_site=wc.website)
                return Notes(link_type="baseurl: found course content")
            except KeyError:
                return Notes(link_type="baseurl: Not found", broken_best_guess="Yes")

        if url.path == "":
            return Notes(link_type="within-page link")

        if "resolveuid" in url.path:
            return Notes(link_type="Broken resolveuid link")
        if "images/inacessible" in url.path:
            return Notes(link_type="image/inaccessible")
        if "icon-question" in url.path:
            return Notes(link_type="icon-question")
        if "images/trans.gif" in url.path:
            return Notes(link_type="images/trans.gif")
        if "mp_logo" in url.path:
            return Notes(link_type="mit_press_logo")
        if "faq-technical-requirements" in url.path:
            return Notes(
                link_type="faq-technical-requirements (https://ocw.mit.edu/help/faq-technical-requirements/)"
            )
        if "fair-use" in url.path or "fairuse" in url.path:
            return Notes(link_type="fairuse (https://ocw.mit.edu/help/faq-fair-use/)")
        if url.path.rstrip("/").endswith("/terms"):
            return Notes(link_type="terms (https://ocw.mit.edu/terms/)")
        if "images/educator/edu_" in url.path:
            return Notes(
                link_type='image/educate/edu_ ... used for "Semester Breakdown" on https://ocw.mit.edu/courses/sloan-school-of-management/15-279-management-communication-for-undergraduates-fall-2012/instructor-insights/'
            )
        if url.path.startswith("/ans7870"):
            return Notes(link_type="/ans7870")
        if url.path.startswith("/20-219IAP15"):
            return Notes(
                link_type="/20-219IAP15 ... (redirects https://ocw.mit.edu/courses/biological-engineering/20-219-becoming-the-next-bill-nye-writing-and-hosting-the-educational-show-january-iap-2015/) "  # noqa: E501
            )
        if url.path == "/images/a_logo_17.gif":
            return Notes(link_type="/images/a_logo_17.gif")
        if url.path.endswith("button_start.png"):
            return Notes(link_type="button_start.png")
        if "images/educator/classroom_" in url.path:
            return Notes(link_type="images/educator/classroom_")

        return Notes(link_type="Unknown", broken_best_guess="Yes")
