"""Management command to sync captions and transcripts for any videos missing them from 3play API"""  # noqa: E501

from django.db.models import Q

from main.management.commands.filter import WebsiteFilterCommand
from videos.threeplay_sync import sync_video_captions_and_transcripts
from websites.models import WebsiteContent


class Command(WebsiteFilterCommand):
    """Check for WebContent with missing caption/transcripts, and syncs via 3play API"""

    help = __doc__

    def __init__(self):
        super().__init__()

        self.missing_results = {"count": 0}
        summary_boilerplate = {
            "total": 0,
            "missing": 0,
            "updated": 0,
            "missing_details": [],
        }
        self.summary = {
            "captions": summary_boilerplate.copy(),
            "transcripts": summary_boilerplate.copy(),
        }

    def handle(self, *args, **options):
        def write_stdout(msg: str, *args) -> None:
            self.stdout.write(msg % args)

        super().handle(*args, **options)

        content_videos = WebsiteContent.objects.filter(
            Q(metadata__resourcetype="Video")
            & (
                Q(metadata__video_files__video_captions_file=None)
                | Q(metadata__video_files__video_transcript_file=None)
            )
        )
        content_videos = self.filter_website_contents(content_videos)

        if not content_videos:
            self.stdout.write("No courses found")
            return

        for video in content_videos:
            youtube_id = video.metadata["video_metadata"]["youtube_id"]
            sync_video_captions_and_transcripts(
                video,
                self.summary,
                self.missing_results,
                write_output=write_stdout,
            )

        for item_type, details in self.summary.items():
            self.stdout.write(
                f"Updated {details['updated']}/{details['total']} {item_type}, missing ({details['missing']}) details are listed below,"  # noqa: E501
            )
            for youtube_id, course in details["missing_details"]:
                self.stdout.write(f"{youtube_id} of course {course}")

        self.stdout.write(
            f"\nCaptions: {self.summary['captions']['updated']} updated, {self.summary['captions']['missing']} missing, {self.summary['captions']['total']} total\n"  # noqa: E501
            f"Transcripts: {self.summary['transcripts']['updated']} updated, {self.summary['transcripts']['missing']} missing, {self.summary['transcripts']['total']} total\n"  # noqa: E501
            f"Found captions or transcripts for {len(content_videos) - self.missing_results['count']}/{len(content_videos)} videos"  # noqa: E501
        )
