""" Import OCW course sites and content via ocw2hugo output """
import pydoc

from django.conf import settings
from django.core.management import BaseCommand
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import sync_unsynced_websites
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
            default=10,
            type=int,
            help="Number of courses to process per celery task (default 10)",
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
        parser.add_argument(
            "-cb",
            "--create_backend",
            dest="create_backend",
            action="store_true",
            help="Create backends if they don't exist",
        )
        parser.add_argument(
            "-d",
            "--delete_unpublished",
            dest="delete_unpublished",
            default=True,
            type=bool,
            help="If True, delete all courses that have been unpublished in the source data",
        )
        parser.add_argument(
            "--git_delete",
            dest="delete_from_git",
            action="store_true",
            help="If included, delete any git repo files that don't match WebsiteContent filepaths",
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
        delete_unpublished = options["delete_unpublished"]
        delete_from_git = options["delete_from_git"]

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
            delete_unpublished=delete_unpublished,
            chunk_size=options["chunks"],
        )
        self.stdout.write(f"Starting task {task}...")
        task.get()
        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "OCW course import finished, took {} seconds".format(total_seconds)
        )

        if options["sync"] is True and settings.CONTENT_SYNC_BACKEND:
            self.stdout.write("Syncing all unsynced courses to the designated backend")
            start = now_in_utc()
            task = sync_unsynced_websites.delay(
                create_backends=options["create_backend"],
                delete=delete_from_git,
            )
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )
