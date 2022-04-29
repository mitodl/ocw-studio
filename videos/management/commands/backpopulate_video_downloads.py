"""
Move 16:9 transcoded videos into the correct S3 paths for syncing, and update the resource
metadata to point to that path for downloads.
"""

import os

from django.conf import settings
from django.core.management import BaseCommand, CommandParser
from google_auth_oauthlib.flow import InstalledAppFlow
from mitol.common.utils import now_in_utc

from content_sync.tasks import sync_unsynced_websites
from videos.api import prepare_video_download_file
from videos.models import Video


script_path = os.path.dirname(os.path.realpath(__file__))


class Command(BaseCommand):
    """
    Move 16:9 transcoded videos into the correct S3 paths for syncing, and update the resource
    metadata to point to that path for downloads.
    """

    help = __doc__

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process videos for sites with names in this comma-delimited list",
        )
        parser.add_argument(
            "-ss",
            "--skip-sync",
            dest="skip_sync",
            action="store_true",
            default=False,
            help="Whether to skip running the sync_unsynced_websites task",
        )

    def handle(self, *args, **options):
        """
        Run the command
        """
        filter = [name.strip() for name in options["filter"].split(",") if name]
        is_verbose = options["verbosity"] > 1

        videos = Video.objects.all()
        if filter:
            videos.filter(website__name__in=filter)

        self.stdout.write(
            f"Updating downloadable video files for {videos.count()} sites."
        )
        for video in videos:
            if is_verbose:
                self.stdout.write(
                    f"Updating video {video.source_key} for site {video.website.name}"
                )
            try:
                prepare_video_download_file(video)
            except Exception as exc:
                self.stderr.write(
                    f"Error Updating video {video.source_key} for site {video.website.name}: {exc}"
                )
        self.stdout.write(
            f"Completed Updating downloadable video files for {videos.count()} sites."
        )

        if settings.CONTENT_SYNC_BACKEND and not options["skip_sync"]:
            self.stdout.write("Syncing all unsynced websites to the designated backend")
            start = now_in_utc()
            task = sync_unsynced_websites.delay(create_backends=True)
            self.stdout.write(f"Starting task {task}...")
            task.get()
            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                "Backend sync finished, took {} seconds".format(total_seconds)
            )
