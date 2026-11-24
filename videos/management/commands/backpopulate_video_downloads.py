"""
Move 16:9 transcoded videos into the correct S3 paths for syncing,
and update the resource metadata to point to that path for downloads.
"""

from typing import TYPE_CHECKING

from content_sync.management.utils import sync_repaired_content
from main.management.commands.filter import WebsiteFilterCommand
from videos.api import prepare_video_download_file
from videos.models import Video

if TYPE_CHECKING:
    from django.core.management import CommandParser


class Command(WebsiteFilterCommand):
    """
    Move 16:9 transcoded videos into the correct S3 paths for syncing,
    and update the resource metadata to point to that path for downloads.
    """

    help = __doc__

    def add_arguments(self, parser: CommandParser) -> None:
        """Add arguments to the command's argument parser."""
        super().add_arguments(parser)
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
        super().handle(*args, **options)
        is_verbose = options["verbosity"] > 1

        videos = Video.objects.all()
        videos = self.filter_videos(videos=videos)

        self.stdout.write(
            f"Updating downloadable video files for {videos.count()} videos."
        )
        with sync_repaired_content(self.stdout, enabled=not options["skip_sync"]):
            for video in videos:
                if is_verbose:
                    self.stdout.write(
                        f"Updating video {video.source_key}"
                        f" for site {video.website.short_id}"
                    )
                try:
                    prepare_video_download_file(video)
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(
                        f"Error updating video {video.source_key}"
                        f" for site {video.website.short_id}: {exc}"
                    )
            self.stdout.write(
                f"Completed updating downloadable video files for {videos.count()} "
                "videos."
            )
