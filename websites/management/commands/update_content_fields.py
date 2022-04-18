"""Updates multiple fields of content based on starter"""
from argparse import ArgumentTypeError
import re
from django.core.exceptions import FieldDoesNotExist
from django.core.management import BaseCommand, CommandError
from django.db import transaction

from websites.models import WebsiteContent


class Command(BaseCommand):

    help = __doc__

    def _parse_data(self, data):
        tuples = re.findall("([^\d\W]\w*)=(\S+)", data)
        if not tuples:
            raise ArgumentTypeError
        return tuples[0]

    def add_arguments(self, parser):
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

        key_values = options.get("data")
        starter = options.get("starter")
        page_type = options.get("type")

        updated_data = {key: value for key, value in key_values}
        confirmation = input(
            f"""WARNING: You are about to update the '{", ".join(updated_data.keys())}' fields with values '{", ".join(updated_data.values())}' for content type '{page_type}' from the starter '{starter}'.Would you like to proceed with the import? (y/n): """
        )

        if confirmation != "y":
            self.stdout.write("Aborting...")
            return

        with transaction.atomic():
            try:
                WebsiteContent.objects.filter(
                    website__starter__slug=starter, type=page_type
                ).update(**updated_data)
            except FieldDoesNotExist as e:
                raise CommandError(e)
