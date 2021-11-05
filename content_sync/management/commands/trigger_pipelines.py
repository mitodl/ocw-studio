""" Trigger website pipeline builds"""
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc
from requests import HTTPError

from content_sync.api import get_sync_pipeline
from websites.constants import STARTER_SOURCE_GITHUB
from websites.models import Website


class Command(BaseCommand):
    """ Trigger all draft or live website pipeline builds """

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
            "-s",
            "--starter",
            dest="starter",
            default="",
            help="If specified, only trigger pipelines for websites that are based on this starter slug",
        )

    def handle(self, *args, **options):

        if not settings.CONTENT_SYNC_PIPELINE:
            self.stderr.write("Pipeline backend is not configured")
            return

        self.stdout.write("Triggering website pipelines")
        start = now_in_utc()

        filter_str = options["filter"].lower()
        version = options["version"].lower()
        starter_str = options["starter"]
        is_verbose = options["verbosity"] > 1

        total_pipelines = 0

        website_qset = Website.objects.filter(starter__source=STARTER_SOURCE_GITHUB)
        if filter_str:
            website_qset = website_qset.filter(
                Q(name__icontains=filter_str) | Q(title__icontains=filter_str)
            )
        if starter_str:
            website_qset = website_qset.filter(starter__slug=starter_str)

        for website in website_qset.iterator():
            pipeline = get_sync_pipeline(website)
            try:
                build_id = pipeline.trigger_pipeline_build(version)
                Website.objects.filter(pk=website.pk).update(
                    **{
                        "latest_build_id_draft"
                        if version == "draft"
                        else "latest_build_id_live": build_id
                    }
                )
                total_pipelines += 1
                if is_verbose:
                    self.stdout.write(f"{website.name} pipeline triggered")
            except HTTPError as err:
                if err.response.status_code == 404:
                    self.stderr.write(f"No pipeline exists for website {website.name}")
                else:
                    self.stderr.write(
                        f"Error triggering pipeline for website {website.name}: {err}"
                    )

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Website pipeline triggers finished, took {} seconds".format(total_seconds)
        )
        self.stdout.write(f"{total_pipelines} pipelines triggered")
