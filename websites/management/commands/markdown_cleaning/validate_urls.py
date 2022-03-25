import re
from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import ContentLookup
from websites.models import WebsiteContent


class ValidateUrls(RegexpCleanupRule):
    """
    This rule never changes anything. Its intent is to find links and validate
    that they work.
    """

    regex = (
        # Do not try to capture link text, else we'll miss images inside links
        # because the regex matches will overlap
        r"\\?\]"  # title closing "]" (or "\]")
        + r"\("  # url open
        + r"(?P<url>[^\s]*?)"  # capture the url
        + r"(\s\"(?P<title>.*?)\")?"  # capture optional title
        + r"\)"  # url close
    )

    alias = "validate_urls"

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
        url_path: str
        links_to_course: str = ""
        broken_best_guess: str = "Yes"

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

    def replace_match(self, match: re.Match, wc: WebsiteContent):
        url = urlparse(match.group("url"))
        original_text = match[0]
        notes = partial(self.ReplacementNotes, url_path=url.path)
        note_works = partial(notes, broken_best_guess="No")
        note_broken = partial(notes, broken_best_guess="Yes")

        if url.scheme.startswith("http"):
            return original_text, note_works(link_type="external link")
        if url.scheme.startswith("ftp"):
            return original_text, note_works(link_type="ftp")
        if url.scheme.startswith("mailto"):
            return original_text, note_works(link_type="mailto")

        if url.path.startswith("/courses"):

            try:
                linked_content = self.content_lookup.find(url.path)
                return original_text, note_works(
                    link_type="course content",
                    links_to_course=linked_content.website.name,
                )
            except KeyError:
                pass

            if url.path.endswith("_index.html"):
                return original_text, note_broken("Fix underway: _index.html")

        if url.path.lstrip("/").startswith("course") and "." in url.path[-8:]:
            return original_text, note_broken("Fix underway: File issue")
        if url.path.lstrip("/").startswith("resource") and "." in url.path[-8:]:
            return original_text, note_broken("Fix underway: File issue")

        if url.path == "":
            return original_text, note_works("within-page link")

        if "resolveuid" in url.path:
            return original_text, note_broken("resolveuid link")
        if "images/inacessible" in url.path:
            return original_text, note_broken("image/inaccessible")
        if "icon-question" in url.path:
            return original_text, note_broken("icon-question")
        if "images/trans.gif" in url.path:
            return original_text, note_broken("images/trans.gif")
        if "mp_logo" in url.path:
            return original_text, note_broken("mit_press_logo")
        if "faq-technical-requirements" in url.path:
            return original_text, note_broken(
                "faq-technical-requirements (https://ocw.mit.edu/help/faq-technical-requirements/)"
            )
        if "fair-use" in url.path or "fairuse" in url.path:
            return original_text, note_broken(
                "fairuse (https://ocw.mit.edu/help/faq-fair-use/)"
            )
        if url.path.rstrip("/").endswith("/terms"):
            return original_text, note_broken("terms (https://ocw.mit.edu/terms/)")
        if "images/educator/edu_" in url.path:
            return original_text, note_broken(
                'image/educate/edu_ ... used for "Semester Breakdown" on https://ocw.mit.edu/courses/sloan-school-of-management/15-279-management-communication-for-undergraduates-fall-2012/instructor-insights/'
            )
        if url.path.startswith("/ans7870"):
            return original_text, note_broken("/ans7870 (TODO: investigate)")
        if url.path.startswith("/20-219IAP15"):
            return original_text, note_broken(
                "/20-219IAP15 ... (redirects https://ocw.mit.edu/courses/biological-engineering/20-219-becoming-the-next-bill-nye-writing-and-hosting-the-educational-show-january-iap-2015/) "
            )
        if url.path == "/images/a_logo_17.gif":
            return original_text, note_broken("/images/a_logo_17.gif")
        if url.path.endswith("button_start.png"):
            return original_text, note_broken("button_start.png")
        if "images/educator/classroom_" in url.path:
            return original_text, note_broken("images/educator/classroom_")

        return original_text, note_broken("Unknown")
