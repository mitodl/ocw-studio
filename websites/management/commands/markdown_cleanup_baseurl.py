"""Replace baseurl-based links with resource_link shortcodes."""
import importlib
import os
import re
from contextlib import ExitStack
from typing import Iterable

from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from django.db import transaction

from websites.management.commands.util import (
    WebsiteContentMarkdownCleaner,
    progress_bar,
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


class BaseurlReplacer:
    """Replacer function for use with WebsiteContentMarkdownCleaner. Replaces
    baseurl links with < resource_link > shortcodes.

    This is intentially limited in scope for now. Some baseurl links, such as
    those whose titles are images or include square brackets, are excluded from
    replacement.
    """

    baseurl_regex = r"\[(?P<title>[^\[\]\n]*?)\]\({{< baseurl >}}(?P<url>.*?)\)"

    def __init__(self, content_lookup: ContentLookup):
        self.content_lookup = content_lookup

    def __call__(self, match: re.Match, website_content: WebsiteContent):
        original_text = match[0]
        escaped_title = match.group("title").replace('"', '\\"')
        url = match.group("url")

        try:
            linked_content = self.content_lookup.get_content_by_url(
                website_content.website_id, url
            )
            return (
                f'{{{{< resource_link {linked_content.text_id} "{escaped_title}" >}}}}'
            )
        except KeyError:
            return original_text


class Command(BaseCommand):
    """
    Replaces baseurl-based links in markdown with < resource_link > shortcodes.
    """

    help = __doc__

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-o",
            "--out",
            dest="out",
            default=None,
            help="If provided, a CSV file of baseurl-based links and their replacements will be written to this path.",
        )
        parser.add_argument(
            "-c",
            "--commit",
            dest="commit",
            default=False,
            help="Whether the changes to markdown should be commited. The default, False, is useful for QA and testing when combined with --out parameter.",
        )
        super().add_arguments(parser)

    def validate_options(self, options):
        """Validate options passed to command."""
        if not options["commit"] and not options["out"]:
            raise ValueError("If --commit is falsy, --out should be provided")

    def handle(self, *args, **options):
        self.validate_options(options)
        self.do_handle(**options)

    @staticmethod
    def do_handle(commit=False, out=None):
        """Replace baseurl with resource_link"""

        with ExitStack() as stack:
            wc_list = WebsiteContent.all_objects.all().only(
                "dirpath", "filename", "markdown", "website_id"
            )
            if commit:
                stack.enter_context(transaction.atomic())
                wc_list.select_for_update()

            content_lookup = ContentLookup(wc_list)
            replacer = BaseurlReplacer(content_lookup)
            cleaner = WebsiteContentMarkdownCleaner(
                BaseurlReplacer.baseurl_regex, replacer
            )

            wc: WebsiteContent
            for wc in progress_bar(wc_list):
                cleaner.update_website_content_markdown(wc)

            if commit:
                wc_list.bulk_update(cleaner.updated_website_contents, ["markdown"])

        if out is not None:
            outpath = os.path.normpath(os.path.join(os.getcwd(), out))
            cleaner.write_matches_to_csv(outpath)
