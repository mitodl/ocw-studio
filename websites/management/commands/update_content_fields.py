"""Updates multiple fields of content based on starter"""
from django.core.exceptions import FieldDoesNotExist
from django.core.management import BaseCommand, CommandError
from django.db import transaction

from websites.models import WebsiteContent


class Command(BaseCommand):

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "starter",
            help="The WebsiteStarter slug to process",
        )

        parser.add_argument(
            "-t",
            "--type",
            dest="type",
            default="testimonials",
            help="The type of content to process",
        )

        parser.add_argument(
            "-k",
            "--keys",
            dest="keys",
            nargs="+",
            default=["type", "dirpath"],
        )

        parser.add_argument(
            "-d",
            "--data",
            dest="data",
            nargs="+",
            default=["stories", "content/stories"],
        )

    def is_valid(self, fields, values):
        return len(fields) == len(values)

    def handle(self, *args, **options):

        fields = options.get("keys")
        values = options.get("data")
        starter = options.get("starter")
        page_type = options.get("type")

        if not self.is_valid(fields, values):
            raise CommandError("The number of arguments for keys should match data")

        updated_data = {x: y for x, y in zip(fields, values)}
        with transaction.atomic():
            try:
                WebsiteContent.objects.filter(
                    website__starter__slug=starter, type=page_type
                ).update(**updated_data)
            except FieldDoesNotExist as e:
                raise CommandError(e)
