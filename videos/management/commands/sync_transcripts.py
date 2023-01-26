"""Management command to sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""

from django.core.management import BaseCommand
from django.db.models import Q

from websites.models import Website, WebsiteContent


class Command(BaseCommand):
    """Sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "--from_course",
            dest="from_course",
            help="name or short_id of course to use as source for sync",
            required=True,
        )

        parser.add_argument(
            "--to_course",
            dest="to_course",
            help="name or short_id of course to use as destination for sync",
            required=True,
        )

    def handle(self, *args, **options):
        from_course = Website.objects.get(
            Q(short_id=options["from_course"]) | Q(name=options["from_course"])
        )
        to_course = Website.objects.get(
            Q(short_id=options["to_course"]) | Q(name=options["to_course"])
        )
        from_course_videos = WebsiteContent.objects.filter(
            Q(website__name=from_course.name) & Q(metadata__resourcetype="Video")
        )
        to_course_videos = WebsiteContent.objects.filter(
            Q(website__name=to_course.name) & Q(metadata__resourcetype="Video")
        )
        from_course_youtube = self.courses_to_youtube_dict(from_course_videos)
        to_course_youtube = self.courses_to_youtube_dict(to_course_videos)
        captions_ctr, transcript_ctr = 0, 0
        for video in to_course_youtube:
            if to_course_youtube[video][0] is None:  # missing captions
                self.stdout.write("Missing captions: " + video + "\n")
                if (
                    video in from_course_youtube
                    and from_course_youtube[video][0] is not None
                ):
                    captions_ctr += 1
                    self.stdout.write("Captions found in source course. Syncing.\n")
            if to_course_youtube[video][1] is None:  # missing transcript
                self.stdout.write("Missing transcript: " + video + "\n")
                if (
                    video in from_course_youtube
                    and from_course_youtube[video][1] is not None
                ):
                    transcript_ctr += 1
                    self.stdout.write("Transcript found in source course. Syncing.\n")
        self.stdout.write(
            str(captions_ctr)
            + " captions and "
            + str(transcript_ctr)
            + " transcripts successfully synced.\n"
        )

    def courses_to_youtube_dict(self, courses):
        youtube_dict = {}
        for course in courses:
            youtube_dict[course.metadata["video_metadata"]["youtube_id"]] = (
                course.metadata["video_files"]["video_captions_file"],
                course.metadata["video_files"]["video_transcript_file"],
            )
        return youtube_dict
