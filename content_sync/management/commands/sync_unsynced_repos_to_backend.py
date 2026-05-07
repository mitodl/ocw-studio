"""Sync all websites that have not yet been pushed to the content sync backend"""  # noqa: INP001

from django.core.management.base import BaseCommand

from content_sync.api import get_sync_backend
from content_sync.models import ContentSyncState
from websites.models import Website


class Command(BaseCommand):
    """Sync all websites that have not yet been pushed to the content sync backend"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-commits",
            dest="batch_commits",
            action="store_true",
            help=(
                "If this flag is added, split sync commits into smaller batches "
                "(intended for large initial sync operations)."
            ),
        )
        parser.add_argument(
            "--batch-size",
            dest="batch_size",
            type=int,
            default=None,
            help=(
                "Optional commit batch size when --batch-commits is set "
                "(uses backend default when omitted)."
            ),
        )
        parser.add_argument(
            "--starter",
            dest="starter",
            default=None,
            help="If specified, only sync websites based on this starter slug",
        )

    def handle(self, *_args, **options):
        # A website is considered unsynced if none of its content has ever
        # been successfully synced (no non-null synced_checksum).
        synced_website_ids = (
            ContentSyncState.objects.filter(synced_checksum__isnull=False)
            .values_list("content__website_id", flat=True)
            .distinct()
        )
        website_qset = Website.objects.exclude(pk__in=synced_website_ids)
        if options["starter"]:
            website_qset = website_qset.filter(starter__slug=options["starter"])

        total = website_qset.count()
        if total == 0:
            self.stdout.write("No unsynced websites found.")
            return

        self.stdout.write(f"Found {total} unsynced website(s). Starting sync...")

        sync_kwargs = {}
        if options["batch_commits"]:
            sync_kwargs["use_batch_commits"] = True
            if options["batch_size"] is not None:
                sync_kwargs["batch_size"] = options["batch_size"]

        success = 0
        errors = 0
        for website in website_qset.iterator():
            try:
                backend = get_sync_backend(website)
                backend.create_website_in_backend()
                backend.sync_all_content_to_backend(**sync_kwargs)
                success += 1
                if options["verbosity"] > 1:
                    self.stdout.write(f"  Synced: {website.name}")
            except Exception as err:  # noqa: BLE001
                errors += 1
                self.stderr.write(f"  ERROR syncing '{website.name}': {err}")

        self.stdout.write(f"Done. Synced {success} website(s), {errors} error(s).")
