""" Management command for upserting the mass build pipeline """
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_mass_build_sites_pipeline, get_pipeline_api
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.base import BaseMassBuildSitesPipeline


class Command(BaseCommand):
    """ Management command for upserting the mass build pipeline """

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
            help="Delete existing mass publish pipelines first",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating mass build pipelines")

        unpause = options["unpause"]
        delete = options["delete"]
        start = now_in_utc()

        if delete:
            self.stdout.write("Deleting existing mass build pipelines first")
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(names=[BaseMassBuildSitesPipeline.PIPELINE_NAME])
                self.stdout.write("Deleted all mass build pipelines")
            else:
                self.stdout.error("No pipeline api configured")

        for version in (VERSION_DRAFT, VERSION_LIVE):
            pipeline = get_mass_build_sites_pipeline(version)
            pipeline.upsert_pipeline()
            self.stdout.write(f"Created {version} mass build pipeline")
            if unpause:
                pipeline.unpause()
                self.stdout.write(f"Unpaused {version} mass build pipeline")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Pipeline upsert finished, took {} seconds".format(total_seconds)
        )
