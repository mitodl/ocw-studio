""" Backpopulate legacy videos """
from django.conf import settings
from django.core.management import CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import backpopulate_archive_videos
from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import WEBSITE_SOURCE_OCW_IMPORT
from websites.models import Website


class Command(WebsiteFilterCommand):
    """Backpopulate legacy videos"""

    help = __doc__

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
            help="The key prefix before the path section of the URL found in the metadata.video_files.archive_url property on WebsiteContent objects",
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

        if self.filter_list:
            website_qset = Website.objects.filter(
                Q(name__in=self.filter_list) | Q(short_id__in=self.filter_list)
            )
        else:
            website_qset = Website.objects.all()

        website_qset = website_qset.filter(source=WEBSITE_SOURCE_OCW_IMPORT)

        website_names = list(website_qset.values_list("name", flat=True))

        if is_verbose:
            self.stdout.write(
                f"Backpopulating legacy videos for the following sites: {','.join(website_names)}"
            )

        start = now_in_utc()
        task = backpopulate_archive_videos.delay(
            bucket,
            prefix,
            website_names,
            chunk_size=chunk_size,
        )

        self.stdout.write(
            f"Started celery task {task} to backpopulate legacy videos for {len(website_names)} sites"
        )

        self.stdout.write("Waiting on task...")

        result = task.get()
        if set(result) != {True}:
            raise CommandError(f"Some errors occurred: {result}")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Backpopulate finished, took {} seconds".format(total_seconds)
        )
