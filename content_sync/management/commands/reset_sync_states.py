"""Reset ContentSyncState synced checksums to None"""
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.models import ContentSyncState
from content_sync.tasks import sync_unsynced_websites


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
            "-c",
            "--create_backends",
            dest="create_backends",
            action="store_true",
            help="Create backends if they do not exist (and sync them too)",
        )
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process content for sites that start with this text in their name/short_id",
        )
        parser.add_argument(
            "-starter",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only process content for sites that are based on this starter slug",
        )
        parser.add_argument(
            "-source",
            "--source",
            dest="source",
            default="",
            help="If specified, only process content for sites that are based on this source",
        )
        parser.add_argument(
            "-ss",
            "--skip_sync",
            dest="skip_sync",
            action="store_true",
            help="Skip syncing backends",
        )

    def handle(self, *args, **options):

        self.stdout.write("Resetting synced checksums to null")
        start = now_in_utc()

        type_str = options["type"].lower()
        create_backends = options["create_backends"]
        filter_str = options["filter"].lower()
        starter_str = options["starter"].lower()
        source_str = options["source"].lower()
        skip_sync = options["skip_sync"]

        content_qset = ContentSyncState.objects.exclude(synced_checksum__isnull=True)
        if type_str:
            content_qset = content_qset.filter(Q(content__type=type_str))
        if filter_str:
            content_qset = content_qset.filter(
                Q(content__website__name__startswith=filter_str)
                | Q(content__website__short_id__startswith=filter_str)
            )
        if starter_str:
            content_qset = content_qset.filter(
                content__website__starter__slug=starter_str
            )
        if source_str:
            content_qset = content_qset.filter(content__website__source=source_str)

        content_qset.update(synced_checksum=None)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Clearing of content sync state complete, took {} seconds".format(
                total_seconds
            )
        )

        if settings.CONTENT_SYNC_BACKEND and not skip_sync:
            self.stdout.write("Syncing all unsynced websites to the designated backend")
            start = now_in_utc()
            task = sync_unsynced_websites.delay(create_backends=create_backends)
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )
