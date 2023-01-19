"""Management command to sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""

from django.core.management import BaseCommand

from websites.models import WebsiteContent


class Command(BaseCommand):
    """Link the video resource with the UUID video_uuid to the captions resource with captions_uuid and downloadable transcript with transcript_uuid"""

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "--from_course",
            dest="from_course",
            help="",
            required=True,
        )

        parser.add_argument(
            "--to_course",
            dest="to_course",
            help="text_id of captions resource object to be linked",
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
        self.stdout.write("Captions and transcripts successfully synced.\n")
