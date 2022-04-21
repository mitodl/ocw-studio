from functools import reduce

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from websites.models import Website


class Command(BaseCommand):
    def handle(self, *args, **options):
        filter_set = ["21W", "CMS"]
        filter_query_set = [
            "name__istartswith",
            "short_id__istartswith",
        ]

        query_set = Website.objects.filter(
            reduce(
                lambda x, y: x | y,
                [Q(**{key: value}) for key, value in zip(filter_query_set, filter_set)],
            )
        )

        with transaction.atomic():
            for website in query_set.iterator():
                if not website.metadata["departments"]:
                    website.metadata["departments"] = [
                        *website.metadata["departments"],
                        "CMS-W",
                    ]
                    website.save()
