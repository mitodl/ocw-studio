"""videos factories"""
import factory
from django.conf import settings
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from videos.constants import ALL_DESTINATIONS, VideoJobStatus, VideoStatus
from videos.models import Video, VideoFile, VideoJob
from websites.factories import WebsiteFactory


class VideoFactory(DjangoModelFactory):
    """ Factory for Video model"""

    source_key = factory.Sequence(
        lambda n: f"{settings.DRIVE_S3_UPLOAD_PREFIX}/{n}/file_{n}"
    )
    website = factory.SubFactory(WebsiteFactory)
    status = FuzzyChoice(VideoStatus.ALL_STATUSES)

    class Meta:
        model = Video


class VideoFileFactory(DjangoModelFactory):
    """Factory for VideoFile model"""

    video = factory.SubFactory(VideoFactory)
    s3_key = factory.Sequence(
        lambda n: f"{settings.VIDEO_S3_TRANSCODE_PREFIX}/{n}/file_{n}"
    )
    destination = FuzzyChoice(ALL_DESTINATIONS)
    destination_id = factory.Faker("domain_word")

    class Meta:
        model = VideoFile


class VideoJobFactory(DjangoModelFactory):
    """Factory for VideoJob model"""

    video = factory.SubFactory(VideoFactory)
    job_id = factory.Faker("md5")
    status = VideoJobStatus.CREATED

    class Meta:
        model = VideoJob
