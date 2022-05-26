"""
We should update the content disposition for video downloads and transcript downloads to attachment so
they are downloaded instead of opening in a browser
"""
import os

import boto3
import botocore
from django.conf import settings
from django.core.management import BaseCommand

from gdrive_sync.models import DriveFile
from videos.constants import DESTINATION_ARCHIVE, VIDEO_DOWNLOAD_PATTERN
from videos.models import Video, VideoFile


script_path = os.path.dirname(os.path.realpath(__file__))


def overwrite_s3_object(path):
    """Replace s3 object with object with correct metadata"""

    s3 = boto3.resource("s3")
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    extra_args = {
        "Metadata": {"ContentDisposition": "attachment"},
        "MetadataDirective": "REPLACE",
        "ACL": "public-read",
    }

    s3.meta.client.copy({"Bucket": bucket, "Key": path}, bucket, path, extra_args)


class Command(BaseCommand):
    """
    Set video and pdf content disposition to attachment
    """

    help = __doc__

    def handle(self, *args, **options):
        """
        Run the command
        """
        videos = Video.objects.all()

        for video in videos:
            if video.pdf_transcript_file and video.pdf_transcript_file.name:
                try:
                    overwrite_s3_object(video.pdf_transcript_file.name)
                except botocore.exceptions.ClientError:
                    self.stdout.write(
                        f"File {video.pdf_transcript_file.name} not found"
                    )

            video_file = VideoFile.objects.filter(
                video=video,
                destination=DESTINATION_ARCHIVE,
                s3_key__contains=VIDEO_DOWNLOAD_PATTERN,
            ).first()

            if video_file and video_file.s3_key:
                try:
                    overwrite_s3_object(video_file.s3_key)
                except botocore.exceptions.ClientError:
                    self.stdout.write(f"File {video_file.s3_key} not found")

        pdf_files = DriveFile.objects.filter(mime_type="application/pdf")

        for pdf_file in pdf_files:
            try:
                overwrite_s3_object(pdf_file.s3_key)
            except botocore.exceptions.ClientError:
                self.stdout.write(f"File {pdf_file.s3_key} not found")
