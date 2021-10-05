""" Backpopulate website pipelines"""
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_sync_backend, get_sync_pipeline
from websites.models import Website


class Command(BaseCommand):
    """ Backpopulate website pipelines """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process websites that contain this filter text in their name",
        )
        parser.add_argument(
            "-s",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only process websites that are based on this starter slug",
        )
        parser.add_argument(
            "-source",
            "--source",
            dest="source",
            default="",
            help="If specified, only process websites that are based on this source",
        )
        parser.add_argument(
            "-c",
            "--create_backends",
            dest="create_backends",
            action="store_true",
            help="Create backends if they do not exist (and sync them too)",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Creating website pipelines")
        start = now_in_utc()

        filter_str = options["filter"].lower()
        starter_str = options["starter"]
        source_str = options["source"]
        is_verbose = options["verbosity"] > 1
        create_backends = options["create_backends"]

        total_websites = 0

        if filter_str:
            website_qset = Website.objects.filter(
                Q(name__icontains=filter_str) | Q(title__icontains=filter_str)
            )
        else:
            website_qset = Website.objects.all()

        if starter_str:
            website_qset = website_qset.filter(starter__slug=starter_str)

        if source_str:
            website_qset = website_qset.filter(source=source_str)

        for website in website_qset.iterator():
            backend = get_sync_backend(website)
            if create_backends:
                backend.create_website_in_backend()
                backend.sync_all_content_to_backend()
            if backend.backend_exists():
                get_sync_pipeline(website).upsert_website_pipeline()
                total_websites += 1

            if is_verbose:
                self.stdout.write(f"{website.name} pipeline created or updated")

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Creation of website pipelines finished, took {} seconds".format(
                total_seconds
            )
        )
        self.stdout.write(f"{total_websites} websites processed")
