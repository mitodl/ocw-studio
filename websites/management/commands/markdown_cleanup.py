"""Replace baseurl-based links with resource_link shortcodes."""
import os
from contextlib import ExitStack

from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from django.db import transaction
from tqdm import tqdm

from websites.management.commands.markdown_cleaning.baseurl_rule import (
    BaseurlReplacementRule,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.legacy_shortcodes_data_fix import (
    LegacyShortcodeFixOne,
    LegacyShortcodeFixTwo,
)
from websites.management.commands.markdown_cleaning.resource_file_rule import (
    ResourceFileReplacementRule,
)
from websites.models import WebsiteContent


class Command(BaseCommand):
    """
    Performs regex replacements on markdown.
    """

    help = __doc__

    Rules = [
        BaseurlReplacementRule,
        ResourceFileReplacementRule,
        LegacyShortcodeFixOne,
        LegacyShortcodeFixTwo,
    ]

    def add_arguments(self, parser: CommandParser) -> None:
        aliases = [R.alias for R in self.Rules]
        parser.add_argument(
            dest="alias",
            help=f"Which rule to run. One of: {aliases}",
        )
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
            action="store_true",
            default=False,
            help="Whether the changes to markdown should be commited. The default, False, is useful for QA and testing when combined with --out parameter.",
        )

    @classmethod
    def validate_options(cls, options):
        """Validate options passed to command."""
        if not options["commit"] and not options["out"]:
            raise ValueError("If --commit is falsy, --out should be provided")
        try:
            next(R for R in cls.Rules if R.alias == options["alias"])
        except StopIteration as not_found:
            aliases = [R.alias for R in cls.Rules]
            raise ValueError(
                f"Rule alias {options['alias']} is invalid. Must be one of {aliases}"
            ) from not_found

    def handle(self, *args, **options):
        self.validate_options(options)
        self.do_handle(
            commit=options["commit"], alias=options["alias"], out=options["out"]
        )

    @classmethod
    def do_handle(cls, alias, commit, out):
        """Replace baseurl with resource_link"""

        with ExitStack() as stack:
            Rule = next(R for R in cls.Rules if R.alias == alias)
            all_wc = WebsiteContent.all_objects.all().only(
                "markdown", "website_id", "text_id"
            )
            if commit:
                stack.enter_context(transaction.atomic())
                all_wc.select_for_update()

            rule = Rule()
            cleaner = WebsiteContentMarkdownCleaner(rule)

            wc: WebsiteContent
            for wc in tqdm(all_wc):
                cleaner.update_website_content_markdown(wc)

            if commit:
                all_wc.bulk_update(cleaner.updated_website_contents, ["markdown"])

        if out is not None:
            outpath = os.path.normpath(os.path.join(os.getcwd(), out))
            cleaner.write_matches_to_csv(outpath)
