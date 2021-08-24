"""Video models"""
from django.db import models
from django.db.models import CASCADE
from mitol.common.models import TimestampedModel

from videos.constants import VideoFileStatus, VideoJobStatus, VideoStatus
from websites.models import Website


class Video(TimestampedModel):
    """ Video object"""

    source_key = models.CharField(max_length=2048, unique=True)
    website = models.ForeignKey(Website, on_delete=CASCADE)
    status = models.CharField(
        max_length=50, null=False, blank=False, default=VideoStatus.CREATED
    )

    def __str__(self):
        return f"'{self.source_key}' ({self.status})"


class VideoFile(TimestampedModel):
    """ Video file created by AWS MediaConvert"""

    video = models.ForeignKey(Video, on_delete=CASCADE, related_name="videofiles")
    s3_key = models.CharField(null=False, blank=False, max_length=2048, unique=True)
    destination = models.CharField(blank=False, null=False, max_length=48)
    destination_id = models.CharField(max_length=256, null=True, blank=True)
    destination_status = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=50, null=False, blank=False, default=VideoFileStatus.CREATED
    )

    def __str__(self):
        return f"'{self.s3_key}' ({self.destination} {self.destination_id})"


class VideoJob(TimestampedModel):
    """ MediaConvert job id per video"""

    job_id = models.CharField(max_length=50, primary_key=True)
    video = models.ForeignKey(Video, on_delete=CASCADE)
    error_code = models.CharField(max_length=24, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=50, null=False, blank=False, default=VideoJobStatus.CREATED
    )

    def __str__(self):
        return f"'{self.job_id}' ({self.status})"
