"""Updates/creates content sync records for website contents"""
from django.db.models import Q

from content_sync.api import upsert_content_sync_state
from main.management.commands.filter import WebsiteFilterCommand
from websites.models import WebsiteContent


class Command(WebsiteFilterCommand):
    """Updates/creates content sync records for website contents"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--content-title",
            dest="content_title",
            help="If provided, only update sync states for website contents that match the given title.",
        )
        parser.add_argument(
            "--text-id",
            dest="text_id",
            help="If provided, only update sync states for website contents with the given text id.",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        filter_qset = {}
        if options["content_title"]:
            filter_qset["title__icontains"] = options["content_title"]
        if options["text_id"]:
            filter_qset["text_id"] = options["text_id"]
        content_qset = WebsiteContent.objects.filter(**filter_qset)
        if self.filter_list:
            content_qset = content_qset.filter(
                Q(website__name__in=self.filter_list)
                | Q(website__short_id__in=self.filter_list)
            )
        num_records = content_qset.count()
        self.stdout.write(
            self.style.WARNING(
                f"Updating content sync state records for {num_records} WebsiteContent objects..."
            )
        )
        for i, content in enumerate(content_qset):
            upsert_content_sync_state(content)
            if i % 1000 == 0:
                self.stdout.write(f"Updated {i} records...")
