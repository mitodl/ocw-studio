"""
Management command to retrieve list of video
captions from YouTube using the YouTube API
"""

import json

from main.management.commands.filter import WebsiteFilterCommand
from videos.youtube import YouTubeApi


class Command(WebsiteFilterCommand):
    """Retrieve list of video captions using YouTube API"""

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--video_ids", nargs="*", type=int, help="List of video IDs"
        )
        parser.add_argument(
            "--youtube_ids", nargs="*", type=str, help="List of YouTube IDs"
        )
        parser.add_argument(
            "--only_dups",
            action="store_true",
            help="Only show videos with duplicate captions",
        )

    def handle(self, *args, **options):
        self.stdout.write("WARNING: This command processes transcoded videos only.")
        self.stdout.write("Videos added directly via YouTube ID are not included.")
        super().handle(*args, **options)
        website_ids = self.filter_list if self.filter_list else None
        video_ids = options["video_ids"] or None
        youtube_ids = options["youtube_ids"] or None

        captions = YouTubeApi.get_all_video_captions(
            website_ids=website_ids,
            video_ids=video_ids,
            youtube_ids=youtube_ids,
            only_dups=options["only_dups"],
        )
        self.stdout.write(json.dumps(captions, indent=2))
