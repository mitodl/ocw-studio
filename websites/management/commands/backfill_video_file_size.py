"""Backfill video file size using archive url"""  # noqa: INP001

from main.management.commands.filter import WebsiteFilterCommand
from videos.tasks import populate_video_file_size
from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.models import Website, WebsiteContent

CHUNK_SIZE = 50


class Command(WebsiteFilterCommand):
    """Backfill metadata['file_size'] for video resources using archive_url"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run the backfill synchronously instead of queuing tasks.",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        sync_execution = options.get("sync", False)

        websites = Website.objects.all()
        websites = self.filter_websites(websites)

        videos = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_RESOURCE,
            metadata__resourcetype=RESOURCE_TYPE_VIDEO,
            website__in=websites,
        )

        videos_to_backfill = []
        for video in videos.iterator():
            metadata = video.metadata or {}
            file_size = metadata.get("file_size")
            archive_url = metadata.get("video_files", {}).get("archive_url")

            if not file_size and archive_url:
                videos_to_backfill.append(video)

        self.stdout.write(
            f"{len(videos_to_backfill)} videos require file_size backfill."
        )
        for i in range(0, len(videos_to_backfill), CHUNK_SIZE):
            chunk = videos_to_backfill[i : i + CHUNK_SIZE]

            for video in chunk:
                self.stdout.write(
                    f"Populating file size for video {video.title} "
                    f"from course {video.website.short_id}"
                )
                try:
                    if sync_execution:
                        populate_video_file_size.run(video.id)
                    else:
                        populate_video_file_size.delay(video.id)
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(
                        f"Failed to populate file size for video {video.title} "
                        f"from course {video.website.short_id}: {exc}"
                    )

            self.stdout.write(f"Finished chunk {i // CHUNK_SIZE + 1}")
