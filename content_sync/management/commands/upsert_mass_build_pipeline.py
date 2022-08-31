""" Management command for upserting the mass build pipeline """
from django.conf import settings
from django.core.management import BaseCommand
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
            "--delete-all",
            dest="delete_all",
            action="store_true",
            help="Delete existing mass publish pipelines first",
        )
        parser.add_argument(
            "-p",
            "--prefix",
            dest="prefix",
            default="",
            help="An optional prefix to prepend to the deploy path",
        )
        parser.add_argument(
            "-t",
            "--themes-branch",
            dest="themes-branch",
            default="",
            help="An optional override for the branch of ocw-hugo-themes to use in the builds",
        )
        parser.add_argument(
            "-r",
            "--projects-branch",
            dest="projects-branch",
            default="",
            help="An optional override for the branch of ocw-hugo-projects to use in the builds",
        )
        parser.add_argument(
            "-o",
            "--offline",
            dest="offline",
            action="store_true",
            help="Upserts an alternate version of the pipeline to mass-build-sites-offline",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating mass build pipelines")

        unpause = options["unpause"]
        delete_all = options["delete_all"]
        prefix = options["prefix"]
        themes_branch = options["themes-branch"]
        projects_branch = options["projects-branch"]
        offline = options["offline"]
        start = now_in_utc()

        if delete_all:
            self.stdout.write("Deleting existing mass build pipelines first")
            api = get_pipeline_api()
            if api:
                api.delete_pipelines(names=[BaseMassBuildSitesPipeline.PIPELINE_NAME])
                self.stdout.write("Deleted all mass build pipelines")
            else:
                self.stdout.error("No pipeline api configured")

        for version in (VERSION_DRAFT, VERSION_LIVE):
            pipeline = get_mass_build_sites_pipeline(
                version,
                prefix=prefix,
                themes_branch=themes_branch,
                projects_branch=projects_branch,
                offline=offline,
            )
            pipeline.upsert_pipeline()
            self.stdout.write(f"Created {version} mass build pipeline")
            if unpause:
                pipeline.unpause()
                self.stdout.write(f"Unpaused {version} mass build pipeline")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Pipeline upsert finished, took {total_seconds} seconds")
