"""Publish live or draft versions of multiple sites"""  # noqa: INP001
from django.conf import settings
from django.core.management import CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import publish_websites
from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import STARTER_SOURCE_GITHUB
from websites.models import Website


class Command(WebsiteFilterCommand):
    """Publish live or draft versions of multiple sites"""

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "version",
            help="The pipeline version to trigger (live or draft)",
        )
        parser.add_argument(
            "-c",
            "--starter",
            dest="starter",
            default=None,
            help="If specified, only trigger pipelines for websites that are based on this starter slug",  # noqa: E501
        )
        parser.add_argument(
            "-s",
            "--source",
            dest="source",
            default=None,
            help="Only trigger pipelines for websites that are based on this source",
        )
        parser.add_argument(
            "-ch",
            "--chunks",
            dest="chunk_size",
            default=500,
            help="Set chunk size for task processing",
        )
        parser.add_argument(
            "-p",
            "--prepublish",
            dest="prepublish",
            action="store_true",
            help="Run prepublish actions on each site",
        )
        parser.add_argument(
            "-nmb",
            "--no-mass-build",
            dest="no_mass_build",
            action="store_true",
            help="Run individual site pipelines instead of the mass-build-sites pipeline",  # noqa: E501
        )

    def handle(self, *args, **options):  # pylint:disable=too-many-locals
        super().handle(*args, **options)
        if not settings.CONTENT_SYNC_PIPELINE_BACKEND:
            self.stderr.write("Pipeline backend is not configured for publishing")
            return

        version = options["version"].lower()
        starter_str = options["starter"]
        source_str = options["source"]
        chunk_size = int(options["chunk_size"])
        prepublish = options["prepublish"]
        no_mass_build = options["no_mass_build"]
        is_verbose = options["verbosity"] > 1

        website_qset = Website.objects.filter(starter__source=STARTER_SOURCE_GITHUB)
        website_qset = self.filter_websites(websites=website_qset)
        website_qset = self.filter_unpublished_websites(
            version=version, websites=website_qset
        )
        if starter_str:
            website_qset = website_qset.filter(starter__slug=starter_str)
        if source_str:
            website_qset = website_qset.filter(source=source_str)

        website_names = list(website_qset.values_list("name", flat=True))

        if no_mass_build:
            confirmation = input(
                f"""WARNING: You are about to trigger individual concourse pipelines for {len(website_names)} sites.
Would you like to proceed? (y/n): """  # noqa: E501
            )
            if confirmation != "y":
                self.stdout.write("Aborting...")
                return

        self.stdout.write(
            f"Publishing {version} version for {len(website_names)} sites."
        )
        start = now_in_utc()
        task = publish_websites.delay(
            website_names,
            version,
            chunk_size=chunk_size,
            prepublish=prepublish,
            no_mass_build=no_mass_build,
        )

        self.stdout.write(
            f"Started task {task} to publish {version} versions for {len(website_names)} sites, source={source_str}"  # noqa: E501
        )

        if is_verbose:
            self.stdout.write(f"{','.join(website_names)}")

        self.stdout.write("Waiting on task...")

        result = task.get()
        if set(result) != {True}:
            msg = "Some errors occurred, check sentry for details"
            raise CommandError(msg)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Publishing tasks finished, took {total_seconds} seconds")
