""" Backpopulate website pipelines"""
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import upsert_pipelines
from websites.models import Website


class Command(BaseCommand):
    """ Backpopulate website pipelines """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process websites that contain this filter text in their name",
        )
        parser.add_argument(
            "-s",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only process websites that are based on this starter slug",
        )
        parser.add_argument(
            "-source",
            "--source",
            dest="source",
            default="",
            help="If specified, only process websites that are based on this source",
        )
        parser.add_argument(
            "-c",
            "--create_backend",
            dest="create_backend",
            action="store_true",
            help="Create backends if they do not exist (and sync them too)",
        )
        parser.add_argument(
            "-ch",
            "--chunks",
            dest="chunk_size",
            default=500,
            help="Set chunk size for task processing",
        )
        parser.add_argument(
            "-u",
            "--unpause",
            dest="unpause",
            action="store_true",
            help="Unpause the pipelines after creating/updating them",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating website pipelines")

        filter_str = options["filter"].lower()
        starter_str = options["starter"]
        source_str = options["source"]
        chunk_size = int(options["chunk_size"])
        create_backend = options["create_backend"]
        is_verbose = options["verbosity"] > 1
        unpause = options["unpause"]

        if filter_str:
            website_qset = Website.objects.filter(
                Q(name__startswith=filter_str) | Q(title__startswith=filter_str)
            )
        else:
            website_qset = Website.objects.all()

        if starter_str:
            website_qset = website_qset.filter(starter__slug=starter_str)

        if source_str:
            website_qset = website_qset.filter(source=source_str)

        website_names = list(website_qset.values_list("name", flat=True))

        if is_verbose:
            self.stdout.write(
                f"Upserting pipelines for the following sites: {','.join(website_names)}"
            )

        start = now_in_utc()
        task = upsert_pipelines.delay(
            website_names,
            chunk_size=chunk_size,
            create_backend=create_backend,
            unpause=unpause,
        )

        self.stdout.write(
            f"Started celery task {task} to upsert pipelines for {len(website_names)} sites"
        )

        self.stdout.write("Waiting on task...")

        result = task.get()
        if set(result) != {True}:
            raise CommandError(f"Some errors occurred: {result}")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Pipeline upserts finished, took {} seconds".format(total_seconds)
        )
