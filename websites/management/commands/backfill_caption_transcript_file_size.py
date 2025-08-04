"""Backfill file and metadata['file_size'] for caption and transcript resources"""  # noqa: INP001

from main.management.commands.filter import WebsiteFilterCommand
from videos.tasks import backfill_caption_or_transcript_file_size
from websites.models import Website, WebsiteContent

CHUNK_SIZE = 50


class Command(WebsiteFilterCommand):
    """Backfill file and metadata['file_size'] for caption and transcript resources"""

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
            type="resource", metadata__resourcetype="Video", website__in=websites
        )

        resources_to_backfill = []

        for video in videos.iterator():
            metadata = video.metadata or {}
            youtube_id = metadata.get("video_metadata", {}).get("youtube_id")
            if not youtube_id:
                continue

            for suffix in ["_transcript", "_captions"]:
                filename = f"{youtube_id}{suffix}"
                resource = WebsiteContent.objects.filter(
                    website=video.website, filename=filename
                ).first()
                if not resource:
                    continue

                if not resource.file or not resource.metadata.get("file_size"):
                    resources_to_backfill.append(resource)

        self.stdout.write(
            f"{len(resources_to_backfill)} caption/transcript resources "
            f"require backfill."
        )

        for i in range(0, len(resources_to_backfill), CHUNK_SIZE):
            chunk = resources_to_backfill[i : i + CHUNK_SIZE]

            for resource in chunk:
                self.stdout.write(
                    f"Populating file size for {resource.filename} "
                    f"from course {resource.website.short_id}"
                )
                try:
                    if sync_execution:
                        backfill_caption_or_transcript_file_size.run(resource.id)
                    else:
                        backfill_caption_or_transcript_file_size.delay(resource.id)
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(
                        f"Failed to backfill {resource.filename} "
                        f"from course {resource.website.short_id}: {exc}"
                    )

            self.stdout.write(f"Finished chunk {i // CHUNK_SIZE + 1}")
