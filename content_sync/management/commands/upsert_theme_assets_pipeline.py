""" Management command for backpopulating the theme pipeline """
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import upsert_theme_assets_pipeline


class Command(BaseCommand):
    """ Backpopulate the theme pipeline """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-u",
            "--unpause",
            dest="unpause",
            action="store_true",
            help="Unpause the pipelines after creating/updating them",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_THEME_PIPELINE:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating theme asset pipeline")

        is_verbose = options["verbosity"] > 1
        unpause = options["unpause"]

        if is_verbose:
            self.stdout.write(f"Upserting theme assets pipeline")

        start = now_in_utc()
        task = upsert_theme_assets_pipeline.delay(unpause=unpause)

        self.stdout.write(f"Started celery task {task} to upsert theme assets pipeline")

        self.stdout.write("Waiting on task...")

        result = task.get()
        if result != True:
            raise CommandError(f"Some errors occurred: {result}")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Pipeline upsert finished, took {} seconds".format(total_seconds)
        )
