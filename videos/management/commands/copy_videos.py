"""
Management command for copying videos from one course to another.
"""
from django.core.management import BaseCommand
from django.db.models import Q

from videos.tasks import copy_video_resource
from websites.models import Website, WebsiteContent


class Command(BaseCommand):
    """
    Management command that copies videos from a source course to a destination course.
    """

    help = "Copy videos from source course to destination course"  # noqa: A003

    def add_arguments(self, parser):
        """Add arguments to the command's argument parser."""
        parser.add_argument(
            "--source_course",
            dest="source_course",
            help="name or short_id of course to use as source for copy",
            type=str,
            required=True,
        )

        parser.add_argument(
            "--destination_course",
            dest="destination_course",
            help="name or short_id of course to use as destination for copy",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--video_uuids", type=str, help="comma-separated list of video UUIDs"
        )

    def get_course(self, course_id_or_name, course_type):
        """
        Retrieve a course by its short_id or name.
        """
        course = Website.objects.filter(
            Q(short_id=course_id_or_name) | Q(name=course_id_or_name)
        ).first()
        if not course:
            self.stdout.write(f"{course_type} {course_id_or_name} not found.")
        return course

    def get_videos(self, source_course, video_uuids):
        """
        Retrieve videos from the source course, optionally filtered by UUIDs.
        """
        source_course_videos = WebsiteContent.objects.filter(
            Q(website__name=source_course.name) & Q(metadata__resourcetype="Video")
        )
        if video_uuids:
            video_uuids = video_uuids.split(",")
            video_uuids = [uuid.strip() for uuid in video_uuids]
            source_course_videos = source_course_videos.filter(text_id__in=video_uuids)
        if not source_course_videos:
            self.stdout.write(
                f"No matching videos found in source course {source_course.name}."
            )
        return source_course_videos

    def handle(self, **options):
        """
        Handle the copying of videos from the source course to the destination course.
        """
        source_course = self.get_course(options["source_course"], "Source course")
        if not source_course:
            return

        destination_course = self.get_course(
            options["destination_course"], "Destination course"
        )
        if not destination_course:
            return

        if source_course == destination_course:
            self.stdout.write("Source and destination courses must be distinct.")
            return

        source_course_videos = self.get_videos(source_course, options["video_uuids"])
        if not source_course_videos:
            return

        for video in source_course_videos:
            video_copy_task = copy_video_resource.delay(
                source_course.uuid, destination_course.uuid, video.text_id
            )
            self.stdout.write(
                f"Started celery task {video_copy_task.id} for video {video.text_id}."
            )
