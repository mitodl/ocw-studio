"""
Management command for copying videos from one course to another.
"""
from django.core.management import BaseCommand
from django.db.models import Q
from mitol.common.utils import now_in_utc

from gdrive_sync.api import get_drive_service
from gdrive_sync.constants import (
    DRIVE_FILE_CREATED_TIME,
    DRIVE_FILE_DOWNLOAD_LINK,
    DRIVE_FILE_ID,
    DRIVE_FILE_MD5_CHECKSUM,
    DRIVE_FILE_MODIFIED_TIME,
    DRIVE_FILE_SIZE,
    DRIVE_FOLDER_FILES_FINAL,
    DriveFileStatus,
)
from gdrive_sync.models import DriveFile
from gdrive_sync.utils import get_gdrive_file, get_resource_name
from videos.models import Video, VideoFile
from videos.utils import create_new_content
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

        self.gdrive_service = get_drive_service()

        for video in source_course_videos:
            self.copy_video_resource(source_course, destination_course, video)

    def copy_gdrive_file(self, gdrive_file, destination_course):
        """
        Copy a Google Drive file to destination course.
        """
        file_id = gdrive_file.get(DRIVE_FILE_ID)
        new_folder_id = destination_course.gdrive_folder
        new_file = (
            self.gdrive_service.files().copy(fileId=file_id, fields="id").execute()
        )

        file = (
            self.gdrive_service.files()
            .get(fileId=new_file.get("id"), fields="parents")
            .execute()
        )
        previous_parents = ",".join(file.get("parents"))
        file = (
            self.gdrive_service.files()
            .update(
                fileId=new_file.get("id"),
                addParents=new_folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            )
            .execute()
        )
        return new_file.get("id")

    def update_transcript_and_captions(
        self, resource, new_transcript_file, new_captions_file
    ):
        """
        Update the associated transcript and captions files for a resource.
        """
        resource.metadata["video_files"]["video_transcript_file"] = str(
            new_transcript_file
        ).lstrip("/")
        resource.metadata["video_files"]["video_captions_file"] = str(
            new_captions_file
        ).lstrip("/")

        resource.save()

    def create_drivefile(self, gdrive_file, new_resource, destination_course):
        """
        Create a DriveFile for gdrive_file in the destination course.
        """
        gdrive_dl = get_gdrive_file(gdrive_file.get(DRIVE_FILE_ID))
        DriveFile.objects.create(
            website_content=new_resource,
            file_id=gdrive_file.get(DRIVE_FILE_ID),
            checksum=gdrive_dl.get(DRIVE_FILE_MD5_CHECKSUM),
            name=get_resource_name(new_resource),
            mime_type=new_resource.metadata["file_type"],
            status=DriveFileStatus.COMPLETE,
            website=destination_course,
            s3_key=str(new_resource.file).lstrip("/"),
            resource=new_resource,
            drive_path=f"{destination_course.short_id}/{DRIVE_FOLDER_FILES_FINAL}",
            modified_time=gdrive_dl.get(DRIVE_FILE_MODIFIED_TIME),
            created_time=gdrive_dl.get(DRIVE_FILE_CREATED_TIME),
            size=gdrive_dl.get(DRIVE_FILE_SIZE),
            download_link=gdrive_dl.get(DRIVE_FILE_DOWNLOAD_LINK),
            sync_dt=now_in_utc(),
        )

    def copy_video_resource(self, source_course, destination_course, source_resource):
        """
        Copy a video resource and associated captions/transcripts.
        """

        video_transcript_file = source_resource.metadata["video_files"][
            "video_transcript_file"
        ]
        video_captions_file = source_resource.metadata["video_files"][
            "video_captions_file"
        ]
        new_resource = create_new_content(source_resource, destination_course)
        if video_transcript_file and video_captions_file:
            video_transcript_resource = WebsiteContent.objects.filter(
                file=video_transcript_file
            ).first()
            new_transcript_resource = create_new_content(
                video_transcript_resource, destination_course
            )
            new_transcript_file = new_transcript_resource.file

            video_captions_resource = WebsiteContent.objects.filter(
                file=video_captions_file
            ).first()
            new_captions_resource = create_new_content(
                video_captions_resource, destination_course
            )
            new_captions_file = new_captions_resource.file

            self.update_transcript_and_captions(
                new_resource, new_transcript_file, new_captions_file
            )
            transcript_gdrive_file = DriveFile.objects.filter(
                s3_key=video_transcript_file
            ).first()
            if transcript_gdrive_file:
                self.copy_gdrive_file(transcript_gdrive_file, destination_course)
                self.create_gdrive_file(
                    transcript_gdrive_file, new_transcript_resource, destination_course
                )
            captions_gdrive_file = DriveFile.objects.filter(
                s3_key=video_captions_file
            ).first()
            if captions_gdrive_file:
                self.copy_gdrive_file(captions_gdrive_file, destination_course)
                self.create_gdrive_file(
                    captions_gdrive_file, new_captions_resource, destination_course
                )

        videofile = VideoFile.objects.filter(
            video__website=source_course,
            destination="youtube",
            destination_id=source_resource.metadata.get("youtube_id"),
        ).first()

        if videofile:
            video = videofile.video
            Video.objects.create(
                website_content=new_resource,
                video_id=video.video_id,
                status=video.status,
            )

            gdrive_file = DriveFile.objects.filter(video=video).first()
            if gdrive_file:
                self.copy_gdrive_file(gdrive_file, destination_course)
                self.create_drivefile(gdrive_file, new_resource, destination_course)
