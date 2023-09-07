"""Updates multiple fields of content based on starter"""  # noqa: INP001
import re
from argparse import ArgumentTypeError

from django.core.exceptions import FieldDoesNotExist
from django.core.management import CommandError
from django.db import transaction
from django.db.models import Q

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import WebsiteContent


class Command(WebsiteFilterCommand):
    """Updates multiple fields of content based on starter"""

    help = __doc__  # noqa: A003

    def _parse_data(self, data):
        """Parse the data"""
        tuples = re.findall(
            r"([^\d\W]\w*)=(\S+)", data
        )  # pylint:disable=anomalous-backslash-in-string
        if not tuples:
            raise ArgumentTypeError
        return tuples[0]

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "starter",
            help="The WebsiteStarter slug to process",
        )

        parser.add_argument(
            "-t",
            "--type",
            dest="type",
            required=True,
            help="The type of content to process",
        )

        parser.add_argument(
            "-d",
            "--data",
            metavar="KEY=VALUE",
            dest="data",
            nargs="+",
            required=True,
            type=self._parse_data,
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        key_values = options.get("data")
        starter = options.get("starter")
        page_type = options.get("type")

        updated_data = dict(key_values)
        confirmation = input(
            f"""WARNING: You are about to update the '{", ".join(updated_data.keys())}' fields with values '{", ".join(updated_data.values())}' for content type '{page_type}' from the starter '{starter}'.Would you like to proceed with the import? (y/n): """  # noqa: E501
        )

        if confirmation != "y":
            self.stdout.write("Aborting...")
            return

        with transaction.atomic():
            try:
                contents = WebsiteContent.objects.filter(
                    website__starter__slug=starter, type=page_type
                )
                if self.filter_list:
                    contents = contents.filter(
                        Q(website__name__in=self.filter_list)
                        | Q(website__short_id__in=self.filter_list)
                    )
                contents.update(**updated_data)
            except FieldDoesNotExist as e:
                raise CommandError(e)  # noqa: B904, TRY200
