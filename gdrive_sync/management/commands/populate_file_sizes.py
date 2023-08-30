"""Populate file_size meta field for resources."""  # noqa: INP001
from django.db.models import Q

from gdrive_sync.tasks import populate_file_sizes_bulk
from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website


class Command(WebsiteFilterCommand):
    """
    Populate file_size metadata for file resources.

    Usage Examples

    ./manage.py populate_file_sizes
    ./manage.py populate_file_sizes --filter course-id
    ./manage.py populate_file_sizes --filter course-id --override-existing
    """

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--override-existing",
            dest="override_existing",
            action="store_true",
            default=False,
            help="Override existing file_size values",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        if self.filter_list:
            website_queryset = Website.objects.filter(
                Q(name__in=self.filter_list) | Q(short_id__in=self.filter_list)
            )
        else:
            website_queryset = Website.objects.all()

        website_names = list(website_queryset.values_list("name", flat=True))

        self.stdout.write("Scheduling populate_file_sizes_bulk...")

        task = populate_file_sizes_bulk.delay(
            website_names, options["override_existing"]
        )

        self.stdout.write("Waiting on task...")

        task.get()

        self.stdout.write("Done")
