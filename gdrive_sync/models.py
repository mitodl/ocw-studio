""" Models for gdrive_sync """
from django.db import models
from mitol.common.models import TimestampedModel

from gdrive_sync.constants import DRIVE_API_RESOURCES, DriveFileStatus
from videos.models import Video
from websites.models import Website, WebsiteContent


class DriveApiQueryTracker(TimestampedModel):
    """ Object for tracking the last google drive api call for a certain resource"""

    api_call = models.CharField(
        null=False,
        blank=False,
        max_length=128,
        unique=True,
        choices=zip(DRIVE_API_RESOURCES, DRIVE_API_RESOURCES),
    )
    for_video = models.BooleanField(default=True, null=False, blank=False)
    last_page = models.CharField(max_length=2048, null=True, blank=True)
    last_dt = models.DateTimeField(null=True, blank=True)


class DriveFile(TimestampedModel):
    """ Model representation of a Google drive file"""

    file_id = models.CharField(
        primary_key=True, null=False, blank=False, max_length=128
    )
    name = models.CharField(null=False, blank=False, max_length=32767)
    mime_type = models.CharField(max_length=256, null=False, blank=False)
    checksum = models.CharField(null=False, blank=False, max_length=32)
    download_link = models.URLField(null=False, blank=False)
    s3_key = models.CharField(max_length=32767, null=True, blank=True)
    status = models.CharField(
        null=False,
        default=DriveFileStatus.CREATED,
        max_length=50,
    )
    modified_time = models.DateTimeField(null=True, blank=True)
    created_time = models.DateTimeField(null=True, blank=True)
    drive_path = models.CharField(null=False, max_length=2048)
    website = models.ForeignKey(Website, null=True, on_delete=models.SET_NULL)
    video = models.ForeignKey(Video, null=True, blank=True, on_delete=models.SET_NULL)
    resource = models.ForeignKey(
        WebsiteContent, null=True, blank=True, on_delete=models.SET_NULL
    )

    def update_status(self, status):
        """ Update the DriveFile status"""
        self.status = status
        self.save()

    def __str__(self):
        return f"'{self.name}' ({self.drive_path} {self.status} {self.file_id})"
