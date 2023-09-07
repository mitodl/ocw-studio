"""Import OCW course sites and content via ocw2hugo output"""
import pydoc

from django.conf import settings
from django.core.management import CommandError
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import sync_unsynced_websites
from main.management.commands.filter import WebsiteFilterCommand
from ocw_import.api import fetch_ocw2hugo_course_paths
from ocw_import.tasks import import_ocw2hugo_courses


class Command(WebsiteFilterCommand):
    """Import OCW course sites and content via ocw2hugo output"""

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)
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
            "--limit",
            dest="limit",
            default=None,
            type=int,
            help="If specified, limits the overall number of course sites imported",
        )
        parser.add_argument(
            "-ss",
            "--skip_sync",
            dest="skip_sync",
            action="store_true",
            help="Do NOT sync all unsynced courses to the backend",
        )
        parser.add_argument(
            "--git_delete",
            dest="delete_from_git",
            action="store_true",
            help="If included, delete any git repo files that don't match WebsiteContent filepaths",  # noqa: E501
        )

    def handle(self, *args, **options):  # pylint:disable=too-many-locals
        super().handle(*args, **options)
        prefix = options["prefix"]
        if prefix:
            # make sure it ends with a '/'
            prefix = prefix.rstrip("/") + "/"
        bucket_name = options["bucket"]
        limit = options["limit"]
        delete_from_git = options["delete_from_git"]

        if len(self.filter_list) < 1:
            msg = "This command cannot be run unfiltered.  Use the --filter or --filter-json argument to specify courses to import."  # noqa: E501
            raise CommandError(msg)

        self.stdout.write(f"Fetching course paths from the '{bucket_name}' bucket...")
        course_paths = list(
            fetch_ocw2hugo_course_paths(
                bucket_name, prefix=prefix, filter_list=self.filter_list
            )
        )

        if options["list"] is True:
            pydoc.pager("\n".join(course_paths))
            return

        confirmation = input(
            f"""WARNING: You are about to destructively import {len(course_paths)} courses from the '{bucket_name}' bucket.
Before you do this, it's recommended that you run with the --list argument to see which courses will be affected by your filter.
Would you like to proceed with the import? (y/n): """  # noqa: E501
        )
        if confirmation != "y":
            self.stdout.write("Aborting...")
            return
        self.stdout.write(f"Importing OCW courses from the '{bucket_name}' bucket...")
        start = now_in_utc()
        task = import_ocw2hugo_courses.delay(
            bucket_name=bucket_name,
            course_paths=course_paths,
            prefix=prefix,
            limit=limit,
            chunk_size=options["chunks"],
        )
        self.stdout.write(f"Starting task {task}...")
        task.get()
        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"OCW course import finished, took {total_seconds} seconds")

        if settings.CONTENT_SYNC_BACKEND and not options["skip_sync"]:
            self.stdout.write("Syncing all unsynced courses to the designated backend")
            start = now_in_utc()
            task = sync_unsynced_websites.delay(
                create_backends=True,
                delete=delete_from_git,
            )
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(f"Backend sync finished, took {total_seconds} seconds")
