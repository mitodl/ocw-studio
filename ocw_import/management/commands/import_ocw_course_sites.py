""" Import OCW course sites and content via ocw2hugo output """
import pydoc

from django.conf import settings
from django.core.management import BaseCommand
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import sync_all_websites
from ocw_import.api import fetch_ocw2hugo_course_paths
from ocw_import.tasks import import_ocw2hugo_courses


class Command(BaseCommand):
    """ Import OCW course sites and content via ocw2hugo output """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-b",
            "--bucket",
            dest="bucket",
            required=True,
            help="Bucket containing ocw2hugo output",
        )
        parser.add_argument(
            "-p",
            "--prefix",
            dest="prefix",
            default="",
            help="S3 Bucket prefix before 'content' or 'data' folder",
        )
        parser.add_argument(
            "-c",
            "--chunks",
            dest="chunks",
            default=100,
            type=int,
            help="Number of courses to process per celery task (default 250)",
        )
        parser.add_argument(
            "-l",
            "--list",
            dest="list",
            action="store_true",
            help="List the course paths instead of importing them",
        )
        parser.add_argument(
            "--filter",
            dest="filter",
            default="",
            help="If specified, only import courses that contain this filter text",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            default=None,
            type=int,
            help="If specified, limits the overall number of course sites imported",
        )
        parser.add_argument(
            "-s",
            "--sync_backend",
            dest="sync",
            action="store_true",
            help="Sync all unsynced courses to the backend",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):
        prefix = options["prefix"]
        if prefix:
            # make sure it ends with a '/'
            prefix = prefix.rstrip("/") + "/"
        bucket_name = options["bucket"]
        filter_str = options["filter"]
        limit = options["limit"]

        if options["list"] is True:
            course_paths = list(
                fetch_ocw2hugo_course_paths(
                    bucket_name, prefix=prefix, filter_str=filter_str
                )
            )
            pydoc.pager("\n".join(course_paths))
            return

        self.stdout.write(f"Importing OCW courses from '{bucket_name}' bucket")
        start = now_in_utc()
        task = import_ocw2hugo_courses.delay(
            bucket_name=bucket_name,
            prefix=prefix,
            filter_str=filter_str,
            limit=limit,
            chunk_size=options["chunks"],
        )
        task.get()
        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "OCW course import finished, took {} seconds".format(total_seconds)
        )

        if options["sync"] is True and settings.CONTENT_SYNC_BACKEND:
            self.stdout.write("Syncing all unsynced courses to the designated backend")
            start = now_in_utc()
            task = sync_all_websites.delay()
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )
