"""Management command to sync captions and transcripts for any videos missing them from one course (from_course) to another (to_course)"""
import re
from copy import deepcopy
from uuid import uuid4

from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q

from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename, get_file_extension
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
        from_course_videos = self.courses_to_youtube_dict(from_course_videos)
        to_course_videos_dict = self.courses_to_youtube_dict(to_course_videos)
        captions_ctr, transcript_ctr = 0, 0
        for video in to_course_videos:
            video_youtube_id = video.metadata["video_metadata"]["youtube_id"]
            if (
                video.metadata["video_files"]["video_captions_file"] is None
            ):  # missing captions
                self.stdout.write("Missing captions: " + video_youtube_id + "\n")
                if (
                    video_youtube_id in to_course_videos_dict
                ):  # captions exist in course
                    captions_ctr += 1
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
                    captions_ctr += 1
                    self.stdout.write("Captions found in source course. Syncing.\n")
                    source_captions = WebsiteContent.objects.get(
                        file=from_course_videos[video_youtube_id][0]
                    )
                    new_captions = self.create_new_content(source_captions, to_course)
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
                    transcript_ctr += 1
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
                    transcript_ctr += 1
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
            str(captions_ctr)
            + " captions and "
            + str(transcript_ctr)
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
                youtube_dict[youtube_id][0] not in [None, captions_file]
                or youtube_dict[youtube_id][1] not in [None, transcript_file]
            ):
                raise ValueError(
                    "Conflicting YouTube ID <-> captions/transcript match in source course."
                )
            if (captions_file is not None) and (transcript_file is not None):
                youtube_dict[youtube_id] = (captions_file, transcript_file)
        return youtube_dict

    def update_metadata(self, source_obj, new_uid, new_s3_path):
        """Generate updated metadata for new WebsiteContent object"""
        new_metadata = deepcopy(source_obj.metadata)
        new_metadata["uid"] = new_uid
        new_metadata["file"] = new_s3_path
        return new_metadata

    def copy_obj_s3(self, source_obj, dest_course):
        """Copy source_obj to the S3 bucket of dest_course"""
        s3 = get_boto3_resource("s3")
        uuid_re = re.compile(
            "^[0-9A-F]{8}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{12}_", re.I
        )
        _, new_filename = get_dirpath_and_filename(str(source_obj.file))
        # remove legacy UUID from filename if it exists
        new_filename = re.split(uuid_re, new_filename)
        if len(new_filename) == 1:
            new_filename = new_filename[0]
        else:
            new_filename = new_filename[1]
        new_filename_ext = get_file_extension(str(source_obj.file))
        if new_filename_ext == "vtt":
            new_filename += "_captions"
        elif new_filename_ext == "pdf":
            new_filename += "_transcript"
        new_s3_path = f"{dest_course.s3_path.rstrip('/')}/{new_filename.lstrip('/')}.{new_filename_ext}"
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_s3_path).copy_from(
            CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME.rstrip('/')}/{str(source_obj.file).lstrip('/')}"
        )
        return new_s3_path

    def create_new_content(self, source_obj, to_course):
        """Create new WebsiteContent object from source_obj in to_course"""
        new_text_id = str(uuid4())
        new_s3_loc = self.copy_obj_s3(source_obj, to_course)
        new_obj_metadata = self.update_metadata(source_obj, new_text_id, new_s3_loc)
        new_obj = WebsiteContent.objects.get_or_create(
            website=to_course,
            text_id=new_text_id,
            defaults={
                "metadata": new_obj_metadata,
                "title": source_obj.title,
                "type": source_obj.type,
                "file": new_s3_loc,
                "dirpath": get_dirpath_and_filename(new_s3_loc)[0],
                "filename": get_dirpath_and_filename(new_s3_loc)[1],
                "is_page_content": True,
            },
        )[0]
        new_obj.save()
        return new_obj
