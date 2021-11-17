""" Publish live or draft versions of multiple sites """
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.constants import VERSION_DRAFT
from content_sync.tasks import publish_websites
from websites.constants import STARTER_SOURCE_GITHUB, WEBSITE_SOURCE_OCW_IMPORT
from websites.models import Website


class Command(BaseCommand):
    """ Publish live or draft versions of multiple sites  """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "version",
            help="The pipeline version to trigger (live or draft)",
        )
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only trigger website pipelines that contain this filter text in their name",
        )
        parser.add_argument(
            "-c",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only trigger pipelines for websites that are based on this starter slug",
        )
        parser.add_argument(
            "-s",
            "--source",
            dest="source",
            default=WEBSITE_SOURCE_OCW_IMPORT,
            help=f"Only trigger pipelines for websites that are based on this source, default is {WEBSITE_SOURCE_OCW_IMPORT}",
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

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE:
            self.stderr.write("Pipeline backend is not configured for publishing")
            return

        filter_str = options["filter"].lower()
        version = options["version"].lower()
        starter_str = options["starter"]
        source_str = options["source"]
        chunk_size = int(options["chunk_size"])
        prepublish = options["prepublish"]
        is_verbose = options["verbosity"] > 1

        self.stdout.write(
            f"Triggering website {version} builds, source is {source_str}"
        )

        website_qset = Website.objects.filter(starter__source=STARTER_SOURCE_GITHUB)
        if filter_str:
            website_qset = website_qset.filter(
                Q(name__icontains=filter_str) | Q(title__icontains=filter_str)
            )
        if starter_str:
            website_qset = website_qset.filter(starter__slug=starter_str)
        if source_str:
            website_qset = website_qset.filter(source=source_str)
            if source_str != WEBSITE_SOURCE_OCW_IMPORT:
                # do not publish any unpublished sites
                if version == VERSION_DRAFT:
                    website_qset = website_qset.exclude(draft_publish_date__isnull=True)
                else:
                    website_qset = website_qset.exclude(publish_date__isnull=True)

        website_names = list(website_qset.values_list("name", flat=True))

        start = now_in_utc()
        task = publish_websites.delay(
            website_names, version, chunk_size=chunk_size, prepublish=prepublish
        )

        self.stdout.write(
            f"Started task {task} to publish {version} versions for {len(website_names)} sites, source={source_str}"
        )

        if is_verbose:
            self.stdout.write(f"{','.join(website_names)}")

        self.stdout.write("Waiting on task...")

        result = task.get()
        if set(result) != {True}:
            raise CommandError("Some errors occurred, check sentry for details")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Publishing tasks finished, took {} seconds".format(total_seconds)
        )
