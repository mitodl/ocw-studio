"""Modify any ContentSyncState.current_checksum values that are out of date"""
import logging

from django.core.paginator import Paginator
from django.db.models import Q
from tqdm import tqdm

from content_sync.models import ContentSyncState
from main.management.commands.filter import WebsiteFilterCommand

log = logging.getLogger(__name__)


class Command(WebsiteFilterCommand):
    """
    Modify any ContentSyncState.current_checksum values that are out of date
    """

    help = __doc__

    def handle(self, *args, **options):
        """
        Iterate through all ContentSyncState objects, calculate checksum, and
        assign to current_checksum value if different.
        """
        super().handle(*args, **options)
        sync_states = (
            ContentSyncState.objects.all().prefetch_related("content").order_by("id")
        )

        if self.filter_list:
            sync_states = sync_states.filter(
                Q(content__website__name__in=self.filter_list)
                | Q(content__website__short_id__in=self.filter_list)
            )

        page_size = 100
        pages = Paginator(sync_states, page_size)
        num_updated = 0
        self.stdout.write(
            f"Comparing checksums for {sync_states.count()} ContentSyncState objects"
        )
        with tqdm(total=pages.count) as progress:
            for page in pages:
                for sync_state in page:
                    checksum = sync_state.content.calculate_checksum()
                    if checksum != sync_state.current_checksum:
                        sync_state.current_checksum = checksum
                        sync_state.save()
                        num_updated += 1
                    progress.update()

        self.stdout.write(f"ContentSyncStates updated: {num_updated}")
