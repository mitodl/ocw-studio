""" Backpopulate website pipelines"""
from django.conf import settings
from django.core.management import CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_pipeline_api
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.tasks import upsert_pipelines
from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website


class Command(WebsiteFilterCommand):
    """ Backpopulate website pipelines """

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
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
            help="Create website backend if it does not exist (and sync it too)",
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
        parser.add_argument(
            "-d",
            "--delete-all",
            dest="delete_all",
            action="store_true",
            help="Delete all existing site pipelines first",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating website pipelines")

        starter_str = options["starter"]
        source_str = options["source"]
        chunk_size = int(options["chunk_size"])
        create_backend = options["create_backend"]
        is_verbose = options["verbosity"] > 1
        unpause = options["unpause"]
        delete_all = options["delete_all"]

        if delete_all:
            self.stdout.write("Deleting all existing site pipelines first")
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(names=[VERSION_LIVE, VERSION_DRAFT])
                self.stdout.write("Deleted all site pipelines")
            else:
                self.stdout.error("No pipeline api configured")

        if self.filter_list:
            website_qset = Website.objects.filter(
                Q(name__in=self.filter_list) | Q(short_id__in=self.filter_list)
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
