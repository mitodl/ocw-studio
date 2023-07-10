""" Update departments metadata for website(s)"""
from functools import reduce

from django.db import transaction
from django.db.models import Q

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import WebsiteContent


class Command(WebsiteFilterCommand):
    """Update departments metadata for website(s)"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-d",
            "--departments",
            dest="departments",
            nargs="*",
            help="Departments to add to the courses",
            required=True,
        )

        parser.add_argument(
            "-s",
            "--startswith",
            dest="startswith",
            nargs="*",
            help="Identifiers to filter websites based on istartswith lookup",
            required=True,
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        startswith = options["startswith"]
        departments = options["departments"]
        startswith_query_set = [
            "website__name__istartswith",
            "website__short_id__istartswith",
        ]

        query_set = WebsiteContent.objects.filter(
            reduce(
                lambda x, y: x | y,
                [
                    Q(**{key: value})
                    for key, value in zip(startswith_query_set, startswith)
                ],
            ),
        )
        if self.filter_list:
            query_set = query_set.filter(
                Q(website__name__in=self.filter_list)
                | Q(website__short_id__in=self.filter_list)
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

        self.stdout.write(
            f"Departmensts successfully updated for {query_set.count()} sites"
        )
