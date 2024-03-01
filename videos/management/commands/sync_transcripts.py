"""Management command to sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""  # noqa: EXE002, E501

from django.core.management import BaseCommand
from django.db.models import Q

from videos.utils import create_new_content
from websites.models import Website, WebsiteContent


class Command(BaseCommand):
    """Sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""  # noqa: E501

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        """Add arguments to the command's argument parser."""
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

    def handle(self, **options):
        """
        Handle the captions/transcript syncing process between the two courses.
        """
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

        from_course_videos = self.courses_to_youtube_dict(from_course_videos)
        ctr = [0, 0]  # captions and transcript counters

        for video in to_course_videos:
            video_youtube_id = video.metadata["video_metadata"]["youtube_id"]
            # refresh query each time
            to_course_videos_dict = self.courses_to_youtube_dict(to_course_videos)
            if (
                video.metadata["video_files"]["video_captions_file"] is None
            ):  # missing captions
                self.stdout.write("Missing captions: " + video_youtube_id + "\n")
                if (
                    video_youtube_id in to_course_videos_dict
                ):  # captions exist in course
                    ctr[0] += 1
                    self.stdout.write(
                        "Captions found in destination course. Syncing.\n"
                    )
                    source_captions = WebsiteContent.objects.filter(
                        Q(website__name=to_course.name)
                        & Q(metadata__file=to_course_videos_dict[video_youtube_id][0])
                    ).first()
                    if not source_captions.is_page_content:
                        source_captions.is_page_content = True
                        source_captions.save()
                    video.metadata["video_files"]["video_captions_file"] = str(
                        source_captions.file
                    )
                    video.save()

                elif (  # create a new captions object
                    video_youtube_id in from_course_videos
                ):
                    ctr[0] += 1
                    self.stdout.write("Captions found in source course. Syncing.\n")
                    source_captions = WebsiteContent.objects.get(
                        file=from_course_videos[video_youtube_id][0]
                    )
                    new_captions = create_new_content(source_captions, to_course)
                    video.metadata["video_files"]["video_captions_file"] = str(
                        new_captions.file
                    )
                    video.save()

            if (
                video.metadata["video_files"]["video_transcript_file"] is None
            ):  # missing transcript
                self.stdout.write("Missing transcript: " + video_youtube_id + "\n")
                if (
                    video_youtube_id in to_course_videos_dict
                ):  # transcript exists in course
                    ctr[1] += 1
                    self.stdout.write(
                        "Transcript found in destination course. Syncing.\n"
                    )
                    source_transcript = WebsiteContent.objects.filter(
                        Q(website__name=to_course.name)
                        & Q(metadata__file=to_course_videos_dict[video_youtube_id][1])
                    ).first()
                    if not source_transcript.is_page_content:
                        source_transcript.is_page_content = True
                        source_transcript.save()
                    video.metadata["video_files"]["video_transcript_file"] = str(
                        source_transcript.file
                    )
                    video.save()
                elif (  # create a new transcript object
                    video_youtube_id in from_course_videos
                ):
                    ctr[1] += 1
                    self.stdout.write("Transcript found in source course. Syncing.\n")
                    source_transcript = WebsiteContent.objects.get(
                        file=from_course_videos[video_youtube_id][1]
                    )
                    new_transcript = self.create_new_content(
                        source_transcript, to_course
                    )
                    video.metadata["video_files"]["video_transcript_file"] = str(
                        new_transcript.file
                    )
                    video.save()

        self.stdout.write(
            str(ctr[0])
            + " captions and "
            + str(ctr[1])
            + " transcripts successfully synced.\n"
        )

    def courses_to_youtube_dict(self, videos):
        """Create a dictionary mapping YouTube IDs to captions/transcripts"""
        youtube_dict = {}
        for video in videos:
            youtube_id = video.metadata["video_metadata"]["youtube_id"]
            captions_file = video.metadata["video_files"]["video_captions_file"]
            transcript_file = video.metadata["video_files"]["video_transcript_file"]
            if youtube_id in youtube_dict and (
                captions_file not in [None, youtube_dict[youtube_id][0]]
                or transcript_file not in [None, youtube_dict[youtube_id][1]]
            ):
                msg = "Conflicting YouTube ID <-> captions/transcript match in source course."  # noqa: E501
                raise ValueError(msg)
            if (captions_file is not None) and (transcript_file is not None):
                youtube_dict[youtube_id] = (captions_file, transcript_file)
        return youtube_dict
