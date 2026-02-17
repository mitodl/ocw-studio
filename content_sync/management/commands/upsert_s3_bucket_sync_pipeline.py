"""Management command for upserting the S3 bucket sync pipeline"""  # noqa: INP001

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_pipeline_api
from content_sync.pipelines.base import BaseS3BucketSyncPipeline
from content_sync.tasks import upsert_s3_bucket_sync_pipeline


class Command(BaseCommand):
    """Upsert the S3 bucket sync pipeline"""

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
            help="Delete existing S3 bucket sync pipeline first",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating S3 bucket sync pipeline")

        is_verbose = options["verbosity"] > 1
        unpause = options["unpause"]
        delete_all = options["delete_all"]

        if is_verbose:
            self.stdout.write("Upserting S3 bucket sync pipeline")

        start = now_in_utc()

        if delete_all:
            self.stdout.write("Delete existing S3 bucket sync pipeline first")
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(names=[BaseS3BucketSyncPipeline.PIPELINE_NAME])
                self.stdout.write("Deleted S3 bucket sync pipeline")
            else:
                self.stderr.write("No pipeline api configured")

        task = upsert_s3_bucket_sync_pipeline.delay(unpause=unpause)
        self.stdout.write(
            f"Started celery task {task} to upsert S3 bucket sync pipeline"
        )
        self.stdout.write("Waiting on task...")

        result = task.get()
        if result is not True:
            msg = f"Some errors occurred: {result}"
            raise CommandError(msg)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Pipeline upsert finished, took {total_seconds} seconds")
