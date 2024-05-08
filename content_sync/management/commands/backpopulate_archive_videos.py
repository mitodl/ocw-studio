"""Backpopulate legacy videos"""  # noqa: INP001
from django.core.management import CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import backpopulate_archive_videos
from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import WEBSITE_SOURCE_OCW_IMPORT
from websites.models import Website


class Command(WebsiteFilterCommand):
    """Backpopulate legacy videos"""

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-b",
            "--bucket",
            dest="bucket",
            required=True,
            help="Bucket containing archive videos",
        )
        parser.add_argument(
            "-p",
            "--prefix",
            dest="prefix",
            default="",
            help="The key prefix before the path section of the URL found in the metadata.video_files.archive_url property on WebsiteContent objects",  # noqa: E501
        )
        parser.add_argument(
            "-ch",
            "--chunks",
            dest="chunk_size",
            default=500,
            help="Set chunk size for task processing",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        bucket = options["bucket"]
        prefix = options["prefix"]
        chunk_size = int(options["chunk_size"])
        is_verbose = options["verbosity"] > 1

        website_qset = Website.objects.filter(source=WEBSITE_SOURCE_OCW_IMPORT)
        website_qset = self.filter_websites(websites=website_qset)

        website_names = list(website_qset.values_list("name", flat=True))

        if is_verbose:
            self.stdout.write(
                f"Backpopulating legacy videos for the following sites: {','.join(website_names)}"  # noqa: E501
            )

        start = now_in_utc()
        task = backpopulate_archive_videos.delay(
            bucket,
            prefix,
            website_names,
            chunk_size=chunk_size,
        )

        self.stdout.write(
            f"Started celery task {task} to backpopulate legacy videos for {len(website_names)} sites"  # noqa: E501
        )

        self.stdout.write("Waiting on task...")

        result = task.get()
        if set(result) != {True}:
            msg = f"Some errors occurred: {result}"
            raise CommandError(msg)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Backpopulate finished, took {total_seconds} seconds")
