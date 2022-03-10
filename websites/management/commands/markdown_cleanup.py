"""Replace baseurl-based links with resource_link shortcodes."""
import os
from contextlib import ExitStack
from typing import Type

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from django.db import transaction
from mitol.common.utils import now_in_utc
from tqdm import tqdm

from content_sync.models import ContentSyncState
from content_sync.tasks import sync_unsynced_websites
from websites.management.commands.markdown_cleaning.baseurl_rule import (
    BaseurlReplacementRule,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.management.commands.markdown_cleaning.legacy_shortcodes_data_fix import (
    LegacyShortcodeFixOne,
    LegacyShortcodeFixTwo,
)
from websites.management.commands.markdown_cleaning.metadata_relative_urls import (
    MetadataRelativeUrlsFix,
)
from websites.management.commands.markdown_cleaning.resource_file_rule import (
    ResourceFileReplacementRule,
)
from websites.management.commands.markdown_cleaning.resource_link_delimiters import (
    ResourceLinkDelimitersReplacementRule,
)
from websites.management.commands.markdown_cleaning.rootrelative_urls import (
    RootRelativeUrlRule,
)
from websites.management.commands.markdown_cleaning.validate_urls import ValidateUrls
from websites.models import WebsiteContent


class Command(BaseCommand):
    """
    Performs regex replacements on markdown and updates checksums.
    """

    help = __doc__

    Rules: "list[Type[MarkdownCleanupRule]]" = [
        BaseurlReplacementRule,
        ResourceFileReplacementRule,
        LegacyShortcodeFixOne,
        LegacyShortcodeFixTwo,
        ResourceLinkDelimitersReplacementRule,
        RootRelativeUrlRule,
        MetadataRelativeUrlsFix,
        ValidateUrls,
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
        parser.add_argument(
            "-ss",
            "--skip-sync",
            dest="skip_sync",
            action="store_true",
            default=False,
            help="Whether to skip running the sync_unsynced_websites task",
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
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )

    @classmethod
    def do_handle(cls, alias, commit, out):
        """Replace baseurl with resource_link"""

        with ExitStack() as stack:
            Rule = next(R for R in cls.Rules if R.alias == alias)
            all_wc = WebsiteContent.all_objects.all().prefetch_related("website")
            if commit:
                stack.enter_context(transaction.atomic())
                all_wc.select_for_update()
            rule = Rule()
            cleaner = WebsiteContentMarkdownCleaner(rule)

            wc: WebsiteContent
            for wc in tqdm(all_wc):
                cleaner.update_website_content(wc)

            if commit:
                all_wc.bulk_update(
                    cleaner.updated_website_contents, Rule.get_root_fields()
                )
                ContentSyncState.objects.bulk_update(
                    cleaner.updated_sync_states, ["current_checksum"]
                )

        if out is not None:
            outpath = os.path.normpath(os.path.join(os.getcwd(), out))
            cleaner.write_matches_to_csv(outpath)
