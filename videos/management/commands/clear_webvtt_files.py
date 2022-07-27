"""
We should save webvtt caption files with the webvtt extensions. This deletes caption files without the extention
from s3 and clears out the video resource metadata so it can be repopulates with the correct extension on publish
"""

import os

from django.conf import settings
from django.core.management import BaseCommand

from main.s3_utils import get_boto3_resource
from videos.models import Video
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.utils import set_dict_field


script_path = os.path.dirname(os.path.realpath(__file__))


class Command(BaseCommand):
    """
    delete _webvtt caption files without extension from s3 and clear resource metadata
    """

    help = __doc__

    def handle(self, *args, **options):
        """
        Run the command
        """

        s3 = get_boto3_resource("s3")
        bucket = settings.AWS_STORAGE_BUCKET_NAME

        videos = Video.objects.filter(
            webvtt_transcript_file__endswith="transcript_webvtt"
        )
        websites = set()
        self.stdout.write(f"Removing {videos.count()} webvtt caption files.")

        for video in videos:
            s3.Object(bucket, video.webvtt_transcript_file.name).delete()
            video.webvtt_transcript_file = None
            video.save()

            websites.add(video.website)

        for website in websites:
            for resource in website.websitecontent_set.filter(
                metadata__resourcetype=RESOURCE_TYPE_VIDEO
            ):
                set_dict_field(resource.metadata, "video_files.video_captions_file", "")
                resource.save()
            self.stdout.write(f"Caption file data cleared for {website.name}")
