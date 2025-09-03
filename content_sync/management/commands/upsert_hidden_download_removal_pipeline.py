"""Management command for upserting the remove-hidden-download-content pipeline"""  # noqa: INP001

from django.conf import settings
from django.core.management import BaseCommand
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_hidden_download_removal_pipeline, get_pipeline_api
from content_sync.pipelines.base import BaseHiddenDownloadContentRemovalPipeline


class Command(BaseCommand):
    """Management command for upserting the remove-hidden-download-content pipeline"""

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
            help="Delete existing hidden download removal pipelines first",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating hidden download content removal pipeline")

        unpause = options["unpause"]
        delete_all = options["delete_all"]
        start = now_in_utc()

        if delete_all:
            self.stdout.write(
                "Delete existing hidden download content removal pipeline first"
            )
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(
                    names=[BaseHiddenDownloadContentRemovalPipeline.PIPELINE_NAME]
                )
                self.stdout.write("Deleted hidden download content removal pipeline")
            else:
                self.stdout.error("No pipeline api configured")

        pipeline = get_hidden_download_removal_pipeline()
        pipeline.upsert_pipeline()
        self.stdout.write("Created hidden download content removal pipeline")
        if unpause:
            pipeline.unpause()
            self.stdout.write("Unpaused hidden download content removal pipeline")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Pipeline upsert finished, took {total_seconds} seconds")
