"""Management command for backpopulating the e2e test pipeline"""  # noqa: INP001
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_pipeline_api
from content_sync.pipelines.base import BaseTestPipeline
from content_sync.tasks import upsert_test_pipeline


class Command(BaseCommand):
    """Backpopulate the end to end testing pipeline"""

    help = __doc__  # noqa: A003

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
            "--delete-all",
            dest="delete_all",
            action="store_true",
            help="Delete existing e2e test pipelines first",
        )
        parser.add_argument(
            "-t",
            "--themes-branch",
            dest="themes_branch",
            help="The branch of ocw-hugo-themes to build against",
        )
        parser.add_argument(
            "-p",
            "--projects-branch",
            dest="projects_branch",
            help="The branch of ocw-hugo-projects to build against",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating end to end testing pipeline")

        is_verbose = options["verbosity"] > 1
        unpause = options["unpause"]
        delete_all = options["delete_all"]
        themes_branch = options["themes_branch"]
        projects_branch = options["projects_branch"]

        if is_verbose:
            self.stdout.write("Upserting end to end testing pipeline")

        start = now_in_utc()

        if delete_all:
            self.stdout.write("Delete existing end to end testing pipelines first")
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(names=[BaseTestPipeline.PIPELINE_NAME])
                self.stdout.write("Deleted end to end testing pipeline")
            else:
                self.stdout.error("No pipeline api configured")

        task = upsert_test_pipeline.delay(
            unpause=unpause,
            themes_branch=themes_branch,
            projects_branch=projects_branch,
        )
        self.stdout.write(
            f"Started celery task {task} to upsert end to end testing pipeline"
        )
        self.stdout.write("Waiting on task...")

        result = task.get()
        if result is not True:
            msg = f"Some errors occurred: {result}"
            raise CommandError(msg)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Pipeline upsert finished, took {total_seconds} seconds")
