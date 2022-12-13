from django.core.management import BaseCommand

from websites.models import WebsiteContent


class Command(BaseCommand):
    """Link the video resource with the UUID video_uuid to the captions resource with captions_uuid and downloadable transcript with transcript_uuid"""

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "--video_uuid",
            dest="video_uuid",
            help="text_id of video resource object to be updated",
            required=True,
        )

        parser.add_argument(
            "--captions_uuid",
            dest="captions_uuid",
            help="text_id of captions resource object to be linked",
            required=True,
        )

        parser.add_argument(
            "--transcript_uuid",
            dest="transcript_uuid",
            help="text_id of downloadable transcript PDF resource object to be linked",
            required=True,
        )

    def handle(self, *args, **options):
        video = WebsiteContent.objects.get(text_id=options["video_uuid"])
        captions = WebsiteContent.objects.get(text_id=options["captions_uuid"])
        video.metadata["video_files"][
            "video_captions_file"
        ] = captions.drivefile_set.first().s3_key
        transcript = WebsiteContent.objects.get(text_id=options["transcript_uuid"])
        video.metadata["video_files"][
            "video_transcript_file"
        ] = transcript.drivefile_set.first().s3_key
        video.save()
        self.stdout.write("Captions and transcript successfully linked to video.\n")
