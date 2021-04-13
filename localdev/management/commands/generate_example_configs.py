""" Iterates through all example site configs in the codebase and generates equivalent files where they're needed """
from django.core.management import BaseCommand

from localdev.configs.api import generate_example_configs


class Command(BaseCommand):
    """
    Iterates through all example site configs in the codebase and generates equivalent files where they're needed
    """

    help = __doc__

    def handle(self, *args, **options):
        written_files = generate_example_configs()
        self.stdout.write(
            self.style.SUCCESS(f"Example config files generated: {written_files}")
        )
