from functools import reduce

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from websites.models import WebsiteContent


class Command(BaseCommand):
    def handle(self, *args, **options):
        filter_set = ["21W", "CMS"]
        filter_query_set = [
            "website__name__istartswith",
            "website__short_id__istartswith",
        ]

        query_set = WebsiteContent.objects.filter(
            reduce(
                lambda x, y: x | y,
                [Q(**{key: value}) for key, value in zip(filter_query_set, filter_set)],
            ),
        )

        query_set = query_set.filter(type="sitemetadata")
        with transaction.atomic():
            for sitemetadata in query_set.iterator():
                if not sitemetadata.metadata["department_numbers"]:
                    sitemetadata.metadata["department_numbers"] = [
                        *sitemetadata.metadata["department_numbers"],
                        "CMS-W",
                    ]
                    sitemetadata.save()
