"""Replace baseurl-based links with resource_link shortcodes."""
import importlib
import os
import re
from typing import Iterable

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.models import WebsiteContent


filepath_migration = importlib.import_module(
    "websites.migrations.0023_website_content_filepath"
)
CONTENT_FILENAME_MAX_LEN = filepath_migration.CONTENT_FILENAME_MAX_LEN
CONTENT_DIRPATH_MAX_LEN = filepath_migration.CONTENT_DIRPATH_MAX_LEN


class ContentLookup:
    """
    Thin wrapper around a dictionary to facilitate looking up WebsiteContent
    objects by their content-relative URL + website id.
    """

    def __init__(self, website_contents: Iterable[WebsiteContent]):
        self.website_contents = {
            (wc.website_id, wc.dirpath, wc.filename): wc for wc in website_contents
        }

    def __str__(self):
        return self.website_contents.__str__()

    @staticmethod
    def standardize_dirpath(content_relative_dirpath):
        """Get dirpath in our database format (see migration 0023)"""
        return "content" + content_relative_dirpath[0:CONTENT_DIRPATH_MAX_LEN]

    @staticmethod
    def standardize_filename(filename):
        """Get filename in our database format (see migration 0023)"""
        return filename[0:CONTENT_FILENAME_MAX_LEN].replace(".", "-")

    def get_content_by_url(self, website_id, content_relative_url: str):
        """Lookup content by its website_id and content-relative URL.

        Example:
        =======
        content_lookup.get_content_by_url('some-uuid', '/resources/graphs/cos')
        """
        try:
            content_relative_dirpath, content_filename = os.path.split(
                content_relative_url
            )
            dirpath = self.standardize_dirpath(content_relative_dirpath)
            filename = self.standardize_filename(content_filename)
            return self.website_contents[(website_id, dirpath, filename)]
        except KeyError:
            dirpath = self.standardize_dirpath(content_relative_url)
            filename = "_index"
            return self.website_contents[(website_id, dirpath, filename)]


def get_all_website_content():
    return WebsiteContent.all_objects.all().only(
        "dirpath", "filename", "markdown", "website_id"
    )


class BaseurlReplacementRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner. Replaces
    baseurl links with < resource_link > shortcodes.

    This is intentially limited in scope for now. Some baseurl links, such as
    those whose titles are images or include square brackets, are excluded from
    replacement.
    """

    regex = (
        r"\\?\[(?P<title>[^\[\]\n]*?)\\?\]"
        + r"\({{< baseurl >}}(?P<url>.*?)"
        + r"(/?#(?P<fragment>.*?))?"
        + r"\)"
    )

    alias = "baseurl"

    def __init__(self):
        website_contents = get_all_website_content()
        self.content_lookup = ContentLookup(website_contents)

    def __call__(self, match: re.Match, website_content: WebsiteContent):
        original_text = match[0]
        escaped_title = match.group("title").replace('"', '\\"')
        url = match.group("url")
        fragment = match.group("fragment")
        if fragment is not None:
            return original_text

        # This is probably a link with image as title, where the image is a < resource >
        if R"{{<" in match.group("title"):
            return original_text

        try:
            linked_content = self.content_lookup.get_content_by_url(
                website_content.website_id, url
            )
            return (
                f'{{{{< resource_link {linked_content.text_id} "{escaped_title}" >}}}}'
            )
        except KeyError:
            return original_text
