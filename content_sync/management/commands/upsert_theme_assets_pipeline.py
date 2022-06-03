""" Management command for backpopulating the theme pipeline """
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_pipeline_api
from content_sync.pipelines.base import BaseThemeAssetsPipeline
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
        parser.add_argument(
            "-d",
            "--delete",
            dest="delete",
            action="store_true",
            help="Delete existing theme assets pipelines first",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating theme asset pipeline")

        is_verbose = options["verbosity"] > 1
        unpause = options["unpause"]
        delete = options["delete"]

        if is_verbose:
            self.stdout.write(f"Upserting theme assets pipeline")

        start = now_in_utc()

        if delete:
            self.stdout.write("Delete existing theme assets pipelines first")
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(names=[BaseThemeAssetsPipeline.PIPELINE_NAME])
                self.stdout.write("Deleted theme assets pipeline")
            else:
                self.stdout.error("No pipeline api configured")

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
