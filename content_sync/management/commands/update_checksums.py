"""Modify any ContentSyncState.current_checksum values that are out of date"""
import json
import logging

from django.core.management import BaseCommand
from django.core.paginator import Paginator
from django.db.models import Q
from tqdm import tqdm

from content_sync.models import ContentSyncState


log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Modify any ContentSyncState.current_checksum values that are out of date
    """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--filter-json",
            dest="filter_json",
            default=None,
            help="If specified, only process sync states for websites specified in a JSON file",
        )
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process sync states for websites with matching names or short_ids",
        )

    def handle(self, *args, **options):
        """
        Iterate through all ContentSyncState objects, calculate checksum, and
        assign to current_checksum value if different.
        """
        sync_states = (
            ContentSyncState.objects.all().prefetch_related("content").order_by("id")
        )
        filter_json = options["filter_json"]
        if filter_json:
            with open(filter_json) as input_file:
                filter_list = json.load(input_file)
        else:
            filter_list = [
                name.strip() for name in options["filter"].split(",") if name
            ]
        if filter_list:
            sync_states = sync_states.filter(
                Q(content__website__name__in=filter_list)
                | Q(content__website__short_id__in=filter_list)
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
