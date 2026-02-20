"""Reset ContentSyncState synced checksums to None"""  # noqa: INP001

from django.conf import settings
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_sync_backend
from content_sync.models import ContentSyncState
from content_sync.tasks import sync_unsynced_websites
from main.management.commands.filter import WebsiteFilterCommand
from websites.api import fetch_website, reset_publishing_fields


class Command(WebsiteFilterCommand):
    """Reset ContentSyncState synced checksums to None"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
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
            "-starter",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only process content for sites that are based on this starter slug",  # noqa: E501
        )
        parser.add_argument(
            "-source",
            "--source",
            dest="source",
            default="",
            help="If specified, only process content for sites that are based on this source",  # noqa: E501
        )
        parser.add_argument(
            "-ss",
            "--skip_sync",
            dest="skip_sync",
            action="store_true",
            help="Skip syncing backends",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        self.stdout.write("Resetting synced checksums to null")
        start = now_in_utc()

        type_str = options["type"].lower()
        create_backends = options["create_backends"]
        starter_str = options["starter"].lower()
        source_str = options["source"].lower()
        skip_sync = options["skip_sync"]

        filtered_websites = []
        if self.filter_list:
            filtered_websites = [
                fetch_website(site_identifier) for site_identifier in self.filter_list
            ]

        content_sync_state_qset = ContentSyncState.objects.exclude(
            synced_checksum__isnull=True
        )
        content_sync_state_qset = self.filter_content_sync_states(
            content_sync_states=content_sync_state_qset
        )
        if type_str:
            content_sync_state_qset = content_sync_state_qset.filter(
                Q(content__type=type_str)
            )
        if starter_str:
            content_sync_state_qset = content_sync_state_qset.filter(
                content__website__starter__slug=starter_str
            )
        if source_str:
            content_sync_state_qset = content_sync_state_qset.filter(
                content__website__source=source_str
            )

        content_sync_state_qset.update(synced_checksum=None, data=None)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            f"Clearing of content sync state complete, took {total_seconds} seconds"
        )

        if settings.CONTENT_SYNC_BACKEND and not skip_sync:
            start = now_in_utc()
            if filtered_websites:
                self.stdout.write(
                    f"Syncing {len(filtered_websites)} filtered "
                    "website(s) to the designated backend"
                )
                for website in filtered_websites:
                    backend = get_sync_backend(website)
                    if create_backends or backend.backend_exists():
                        self.stdout.write(
                            f"Syncing website '{website.title}' to backend..."
                        )
                        backend.create_website_in_backend()
                        backend.sync_all_content_to_backend()
                        reset_publishing_fields(website.name)
                    else:
                        self.stderr.write(
                            f"Skipping website '{website.title}': "
                            "backend does not exist "
                            "(use --create_backends to create it)"
                        )
            else:
                self.stdout.write(
                    "Syncing all unsynced websites to the designated backend"
                )
                task = sync_unsynced_websites.delay(create_backends=create_backends)
                self.stdout.write(f"Starting task {task}...")
                task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(f"Backend sync finished, took {total_seconds} seconds")
