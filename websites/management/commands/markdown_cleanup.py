"""Replace baseurl-based links with resource_link shortcodes."""  # noqa: INP001

import logging
import os

from django.conf import settings
from django.core.management.base import CommandParser
from django.core.paginator import Paginator
from mitol.common.utils import now_in_utc
from tqdm import tqdm

from content_sync.tasks import sync_unsynced_websites
from main.management.commands.filter import WebsiteFilterCommand
from websites.management.commands.markdown_cleaning import (
    MarkdownCleanupRule,
    WebsiteContentMarkdownCleaner,
    rules,
)
from websites.models import WebsiteContent

log = logging.getLogger(__name__)


class Command(WebsiteFilterCommand):
    """
    Performs replacements on markdown. Excludes unpublished websites.

    In general, these commands can be run in any order and are independent from
    one another. It may be useful to run LinkUnescape before other link fixes if
    your data contains (or may contain) markdown links with erroneously escaped
    square brackets.
    """

    help = __doc__

    Rules: "list[type[MarkdownCleanupRule]]" = [
        rules.BaseurlReplacementRule,
        rules.LinkUnescapeRule,
        rules.RootRelativeUrlRule,
        rules.MetadataRelativeUrlsRule,
        rules.ValidateUrlsRule,
        rules.ShortcodeLoggingRule,
        rules.RemoveInaccesibleGifRule,
        rules.LinkLoggingRule,
        rules.LinkWrappedImagesRule,
        rules.ResourceLinkNextPrevRule,
        rules.SubSupFixes,
        rules.LinkResolveuidRule,
        rules.BrokenMarkdownLinkFixRule,
        rules.BrokenMetadataLinkFixRule,
        rules.CourseAbsoluteLinkRule,
        rules.LinkToExternalResourceRule,
        rules.NavItemToExternalResourceRule,
    ]

    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)
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
            help="If provided, a CSV file of baseurl-based links and their replacements will be written to this path.",  # noqa: E501
        )
        parser.add_argument(
            "-c",
            "--commit",
            dest="commit",
            action="store_true",
            default=False,
            help="Whether the changes to markdown should be commited. The default, False, is useful for QA and testing when combined with --out parameter.",  # noqa: E501
        )
        parser.add_argument(
            "-ss",
            "--skip-sync",
            dest="skip_sync",
            action="store_true",
            default=False,
            help="Whether to skip running the sync_unsynced_websites task",
        )
        parser.add_argument(
            "-ch",
            "--csv-only-changes",
            dest="csv_only_changes",
            action="store_true",
            default=False,
            help="Whether to write CSV rows for all matches or only matches that change.",  # noqa: E501
        )
        parser.add_argument(
            "-l",
            "--limit",
            dest="limit",
            type=int,
            default=None,
            help="If supplied, at most this many WebsiteContent pages will be scanned.",
        )

    @classmethod
    def validate_options(cls, options):
        """Validate options passed to command."""
        if not options["commit"] and not options["out"]:
            msg = "If --commit is falsy, --out should be provided"
            raise ValueError(msg)
        try:
            next(R for R in cls.Rules if R.alias == options["alias"])
        except StopIteration as not_found:
            aliases = [R.alias for R in cls.Rules]
            msg = f"Rule alias {options['alias']} is invalid. Must be one of {aliases}"
            raise ValueError(msg) from not_found

    def handle(self, *args, **options):
        super().handle(*args, **options)
        self.validate_options(options)
        website_contents = (
            WebsiteContent.all_objects.all()
            .exclude(website__publish_date__isnull=True)
            .order_by("id")
            .prefetch_related("website")
        )
        website_contents = self.filter_website_contents(
            website_contents=website_contents
        )
        self.do_handle(
            commit=options["commit"],
            alias=options["alias"],
            out=options["out"],
            csv_only_changes=options["csv_only_changes"],
            limit=options["limit"],
            website_contents=website_contents,
        )

        if (
            settings.CONTENT_SYNC_BACKEND
            and options["commit"]
            and not options["skip_sync"]
        ):
            self.stdout.write("Syncing all unsynced websites to the designated backend")
            start = now_in_utc()
            task = sync_unsynced_websites.delay(create_backends=True)
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(f"Backend sync finished, took {total_seconds} seconds")

    @classmethod
    def do_handle(  # noqa: PLR0913
        cls, alias, commit, out, csv_only_changes, limit, website_contents
    ):  # noqa: PLR0913, RUF100
        """Replace baseurl with resource_link"""

        Rule = next(R for R in cls.Rules if R.alias == alias)
        rule = Rule()
        rule.set_options({"commit": commit})

        cleaner = WebsiteContentMarkdownCleaner(rule)

        target_wc = (
            website_contents
            if limit is None
            else website_contents[0 : min(limit, len(website_contents))]
        )
        page_size = 100
        pages = Paginator(target_wc, page_size)

        num_updated = 0
        with tqdm(total=pages.count) as progress:
            for page in pages:
                for wc in page:
                    updated = cleaner.update_website_content(wc)
                    if updated:
                        num_updated += 1
                    if updated and commit:
                        wc.save()
                    progress.update()

        if commit:
            log.info(f"content updated: {num_updated}")  # noqa: G004
        else:
            log.info(f"content that would be updated: {num_updated}")  # noqa: G004

        if out is not None:
            outpath = os.path.normpath(
                os.path.join(os.getcwd(), out)  # noqa: PTH109, PTH118
            )  # noqa: PTH109, PTH118, RUF100
            cleaner.write_matches_to_csv(outpath, only_changes=csv_only_changes)
