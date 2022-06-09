""" Management command for upserting the remove-unpublished-sites pipeline """
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_pipeline_api, get_unpublished_removal_pipeline
from content_sync.pipelines.base import BaseUnpublishedSiteRemovalPipeline


class Command(BaseCommand):
    """ Management command for upserting the remove-unpublished-sites pipeline """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-u",
            "--unpause",
            dest="unpause",
            action="store_true",
            help="Unpause the pipeline after creating/updating it",
        )
        parser.add_argument(
            "-d",
            "--delete-all",
            dest="delete_all",
            action="store_true",
            help="Delete existing site removal pipelines first",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating unpublished sites removal pipeline")

        unpause = options["unpause"]
        delete_all = options["delete_all"]
        start = now_in_utc()

        if delete_all:
            self.stdout.write(
                "Delete existing unpublished sites removal pipeline first"
            )
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(
                    names=[BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME]
                )
                self.stdout.write("Deleted unpublished sites removal pipeline")
            else:
                self.stdout.error("No pipeline api configured")

        pipeline = get_unpublished_removal_pipeline()
        pipeline.upsert_pipeline()
        self.stdout.write(f"Created unpublished sites removal pipeline")
        if unpause:
            pipeline.unpause()
            self.stdout.write(f"Unpaused unpublished sites removal pipeline")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Pipeline upsert finished, took {} seconds".format(total_seconds)
        )
