"""Replace baseurl-based links with resource_link shortcodes."""
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

    def get_content_by_url(self, website_id, content_relative_url: str):
        """Lookup content by its website_id and content-relative URL.

        Example:
        =======
        content_lookup.get_content_by_url('some-uuid', '/resources/graphs/cos')
        """

        content_relative_dirpath, filename = os.path.split(content_relative_url)

        dirpath = f"content{content_relative_dirpath}"

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
            help="If provided, a CSV file of baseurl-based links and their replacements will be written to this path.",
        )
        parser.add_argument(
            "-c",
            "--commit",
            dest="commit",
            help="Whether the changes to markdown should be commited. The default, False, is useful for QA and testing when combined with --out parameter.",
        )
        super().add_arguments(parser)

    def validate_options(self, options):
        """Validate options passed to command."""
        if not options["commit"] and not options["out"]:
            raise ValueError("If --commit is falsy, --out should be provided")

    def handle(self, *args, **options):
        self.validate_options(options)
        commit = options["commit"]

        with ExitStack() as stack:
            wc_list = WebsiteContent.all_objects.all().only(
                "dirpath", "filename", "markdown", "website_id"
            )
            if commit:
                stack.enter_context(transaction.atomic())
                wc_list.select_for_update()

            content_lookup = ContentLookup(wc_list)
            replacer = BaseurlReplacer(content_lookup)
            surgeon = WebsiteContentMarkdownCleaner(
                BaseurlReplacer.baseurl_regex, replacer
            )

            wc: WebsiteContent
            for wc in progress_bar(wc_list):
                surgeon.update_website_content_markdown(wc)

            if commit:
                wc_list.bulk_update(surgeon.updated_website_contents, ["markdown"])

        if "out" in options:
            outpath = os.path.normpath(os.path.join(os.getcwd(), options["out"]))
            surgeon.write_matches_to_csv(outpath)
