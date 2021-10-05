"""Reset ContentSyncState synced checksums to None"""
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.models import ContentSyncState
from content_sync.tasks import sync_all_websites


class Command(BaseCommand):
    """Reset ContentSyncState synced checksums to None"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--type",
            dest="type",
            default="",
            help="If specified, only process content types that match this filter",
        )
        parser.add_argument(
            "-s",
            "--sync_backends",
            dest="sync_backends",
            action="store_true",
            help="Sync all course backends",
        )
        parser.add_argument(
            "-c",
            "--create_backends",
            dest="create_backends",
            action="store_true",
            help="Create backends if they do not exist (and sync them too)",
        )

    def handle(self, *args, **options):

        self.stdout.write("Resetting synced checksums to null")
        start = now_in_utc()

        filter_str = options["type"].lower()
        sync_backends = options["sync_backends"]
        create_backends = options["create_backends"]

        content_qset = ContentSyncState.objects.exclude(synced_checksum__isnull=True)
        if filter_str:
            content_qset = content_qset.filter(Q(content__type=filter_str))

        content_qset.update(synced_checksum=None)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Clearing of content sync state complete, took {} seconds".format(
                total_seconds
            )
        )

        if (sync_backends or create_backends) and settings.CONTENT_SYNC_BACKEND:
            self.stdout.write("Syncing all courses to the designated backend")
            start = now_in_utc()
            task = sync_all_websites.delay(create_backends=create_backends)
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )
