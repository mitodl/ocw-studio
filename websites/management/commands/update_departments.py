from functools import reduce

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from websites.models import WebsiteContent


class Command(BaseCommand):
    def add_arguments(self, parser):

        parser.add_argument(
            "-d",
            "--departments",
            dest="departments",
            nargs="*",
            help="Departments to add to the courses",
            required=True,
        )

        parser.add_argument(
            "-n",
            "--name",
            dest="name",
            nargs="*",
            help="Identifiers to filter websites based on istartswith lookup",
            required=True,
        )

    def handle(self, *args, **options):
        filter_set = options["name"]
        departments = options["departments"]
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
        self.stdout.write(
            f"Total number of websites updated will be {query_set.count()}"
        )
        with transaction.atomic():
            for sitemetadata in query_set.iterator():
                sitemetadata.metadata["department_numbers"] = list(
                    set([*sitemetadata.metadata["department_numbers"], *departments])
                )
                sitemetadata.save()
