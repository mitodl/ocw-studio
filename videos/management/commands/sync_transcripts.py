"""Management command to sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""  # noqa: E501

from django.core.management import BaseCommand
from django.db.models import Q

from videos.utils import create_new_content
from websites.models import Website, WebsiteContent


class Command(BaseCommand):
    """Sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""  # noqa: E501

    help = __doc__

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

    def handle(self, **options):  # noqa: C901, PLR0912, PLR0915
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
            captions_resource = (
                video.metadata["video_files"].get("video_captions_resources") or {}
            )
            if not captions_resource.get("content"):  # missing captions
                self.stdout.write("Missing captions: " + video_youtube_id + "\n")
                if (
                    video_youtube_id in to_course_videos_dict
                    and to_course_videos_dict[video_youtube_id][0]
                ):  # captions exist in course
                    ctr[0] += 1
                    self.stdout.write(
                        "Captions found in destination course. Syncing.\n"
                    )
                    source_captions = WebsiteContent.objects.filter(
                        website=to_course,
                        text_id=to_course_videos_dict[video_youtube_id][0][0],
                    ).first()
                    if source_captions and not source_captions.is_page_content:
                        source_captions.is_page_content = True
                        source_captions.save()
                    if source_captions:
                        video.metadata["video_files"]["video_captions_resources"] = {
                            "content": [str(source_captions.text_id)],
                            "website": to_course.name,
                        }
                        if source_captions.file and source_captions.file.name:
                            file_path = f"/{source_captions.file.name.lstrip('/')}"
                            video.metadata["video_files"]["video_captions_file"] = [
                                {"file": file_path, "language": "en"}
                            ]
                        video.save()

                elif (  # create a new captions object
                    video_youtube_id in from_course_videos
                    and from_course_videos[video_youtube_id][0]
                ):
                    ctr[0] += 1
                    self.stdout.write("Captions found in source course. Syncing.\n")
                    source_captions = WebsiteContent.objects.filter(
                        website=from_course,
                        text_id=from_course_videos[video_youtube_id][0][0],
                    ).first()
                    if source_captions:
                        new_captions = create_new_content(source_captions, to_course)
                        video.metadata["video_files"]["video_captions_resources"] = {
                            "content": [str(new_captions.text_id)],
                            "website": to_course.name,
                        }
                        if new_captions.file and new_captions.file.name:
                            file_path = f"/{new_captions.file.name.lstrip('/')}"
                            video.metadata["video_files"]["video_captions_file"] = [
                                {"file": file_path, "language": "en"}
                            ]
                        video.save()

            transcript_resource = (
                video.metadata["video_files"].get("video_transcript_resources") or {}
            )
            if not transcript_resource.get("content"):  # missing transcript
                self.stdout.write("Missing transcript: " + video_youtube_id + "\n")
                if (
                    video_youtube_id in to_course_videos_dict
                    and to_course_videos_dict[video_youtube_id][1]
                ):  # transcript exists in course
                    ctr[1] += 1
                    self.stdout.write(
                        "Transcript found in destination course. Syncing.\n"
                    )
                    source_transcript = WebsiteContent.objects.filter(
                        website=to_course,
                        text_id=to_course_videos_dict[video_youtube_id][1][0],
                    ).first()
                    if source_transcript and not source_transcript.is_page_content:
                        source_transcript.is_page_content = True
                        source_transcript.save()
                    if source_transcript:
                        video.metadata["video_files"]["video_transcript_resources"] = {
                            "content": [str(source_transcript.text_id)],
                            "website": to_course.name,
                        }
                        if source_transcript.file and source_transcript.file.name:
                            file_path = f"/{source_transcript.file.name.lstrip('/')}"
                            video.metadata["video_files"]["video_transcript_file"] = [
                                {"file": file_path, "language": "en"}
                            ]
                        video.save()
                elif (  # create a new transcript object
                    video_youtube_id in from_course_videos
                    and from_course_videos[video_youtube_id][1]
                ):
                    ctr[1] += 1
                    self.stdout.write("Transcript found in source course. Syncing.\n")
                    source_transcript = WebsiteContent.objects.filter(
                        website=from_course,
                        text_id=from_course_videos[video_youtube_id][1][0],
                    ).first()
                    if source_transcript:
                        new_transcript = create_new_content(
                            source_transcript, to_course
                        )
                        video.metadata["video_files"]["video_transcript_resources"] = {
                            "content": [str(new_transcript.text_id)],
                            "website": to_course.name,
                        }
                        if new_transcript.file and new_transcript.file.name:
                            file_path = f"/{new_transcript.file.name.lstrip('/')}"
                            video.metadata["video_files"]["video_transcript_file"] = [
                                {"file": file_path, "language": "en"}
                            ]
                        video.save()

        self.stdout.write(
            str(ctr[0])
            + " captions and "
            + str(ctr[1])
            + " transcripts successfully synced.\n"
        )

    def courses_to_youtube_dict(self, videos):
        """Map YouTube IDs to (captions_text_ids, transcript_text_ids) tuples."""
        youtube_dict = {}
        for video in videos:
            youtube_id = video.metadata["video_metadata"]["youtube_id"]
            captions_rel = (
                video.metadata["video_files"].get("video_captions_resources") or {}
            )
            transcript_rel = (
                video.metadata["video_files"].get("video_transcript_resources") or {}
            )
            captions_ids = captions_rel.get("content") or []
            transcript_ids = transcript_rel.get("content") or []
            if isinstance(captions_ids, str):
                captions_ids = [captions_ids] if captions_ids else []
            if isinstance(transcript_ids, str):
                transcript_ids = [transcript_ids] if transcript_ids else []
            if youtube_id in youtube_dict and (
                captions_ids not in [[], youtube_dict[youtube_id][0]]
                or transcript_ids not in [[], youtube_dict[youtube_id][1]]
            ):
                msg = "Conflicting YouTube ID <-> captions/transcript match in source course."  # noqa: E501
                raise ValueError(msg)
            if captions_ids or transcript_ids:
                youtube_dict[youtube_id] = (captions_ids, transcript_ids)
        return youtube_dict
