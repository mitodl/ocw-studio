from django.conf import settings  # noqa: INP001
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils import now_in_utc

from gdrive_sync.tasks import create_gdrive_folders_chunked
from websites.models import Website


class Command(BaseCommand):
    """Creates a Google drive folder for websites that don't already have one"""

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process websites whose name/short_id starts with this",  # noqa: E501
        )
        parser.add_argument(
            "-c",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only process websites that have this site config starter slug",  # noqa: E501
        )
        parser.add_argument(
            "-s",
            "--source",
            dest="source",
            default="",
            help="If specified, only process websites that have this type",
        )
        parser.add_argument(
            "-ch",
            "--chunks",
            dest="chunk_size",
            default=500,
            help="Set chunk size for task processing",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
            websites = Website.objects.all()
            website_filter = options["filter"].lower()
            starter_filter = options["starter"].lower()
            source_filter = options["source"].lower()
            chunk_size = int(options["chunk_size"])
            is_verbose = options["verbosity"] > 1

            if website_filter:
                websites = websites.filter(
                    Q(name__startswith=website_filter)
                    | Q(short_id__startswith=website_filter)
                )
            if starter_filter:
                websites = websites.filter(starter__slug=starter_filter)
            if source_filter:
                websites = websites.filter(source=source_filter)

            short_ids = list(websites.values_list("short_id", flat=True))

            start = now_in_utc()
            task = create_gdrive_folders_chunked.delay(short_ids, chunk_size=chunk_size)

            self.stdout.write(
                f"Started celery task {task} to create Google drive folders for {len(short_ids)} sites."  # noqa: E501
            )
            if is_verbose:
                self.stdout.write(f"{','.join(short_ids)}")

            self.stdout.write("Waiting on task...")

            result = task.get()
            if set(result) != {True}:
                msg = f"Some errors occurred: {result}"
                raise CommandError(msg)

            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                f"Google drive folder creation finished, took {total_seconds} seconds"
            )
