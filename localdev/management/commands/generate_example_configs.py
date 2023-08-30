"""Iterates through all example site configs in the codebase and generates equivalent files where they're needed"""  # noqa: E501
from django.core.management import BaseCommand

from localdev.configs.api import generate_example_configs


class Command(BaseCommand):
    """
    Iterates through all example site configs in the codebase and generates equivalent files where they're needed
    """  # noqa: E501

    help = __doc__  # noqa: A003

    def handle(self, *args, **options):  # noqa: ARG002
        written_files = generate_example_configs()
        self.stdout.write(
            self.style.SUCCESS(f"Example config files generated: {written_files}")
        )
