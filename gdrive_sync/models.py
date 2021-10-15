""" Models for gdrive_sync """
import os

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from mitol.common.models import TimestampedModel

from gdrive_sync.constants import (
    DRIVE_API_RESOURCES,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DriveFileStatus,
)
from videos.models import Video
from websites.api import find_available_name
from websites.models import Website, WebsiteContent


class DriveApiQueryTracker(TimestampedModel):
    """ Object for tracking the last google drive api call for a certain resource"""

    api_call = models.CharField(
        null=False,
        blank=False,
        max_length=128,
        choices=zip(DRIVE_API_RESOURCES, DRIVE_API_RESOURCES),
        unique=True,
    )
    last_page = models.CharField(max_length=2048, null=True, blank=True)
    last_dt = models.DateTimeField(null=True, blank=True)


class DriveFile(TimestampedModel):
    """ Model representation of a Google drive file"""

    file_id = models.CharField(
        primary_key=True, null=False, blank=False, max_length=128
    )
    name = models.CharField(null=False, blank=False, max_length=32767)
    mime_type = models.CharField(max_length=256, null=False, blank=False)
    checksum = models.CharField(max_length=32, null=True, blank=True)
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

    def is_video(self):
        """Return True if is is in the video folder"""
        return DRIVE_FOLDER_VIDEOS_FINAL in self.drive_path.split("/")

    def get_valid_s3_key(self) -> str:
        """
        Return a unique s3 key for a DriveFile that will satisfy unique constraints,
        adding/incrementing a numerical suffix as necessary.
        """
        basename, ext = os.path.splitext(self.name)
        basename = slugify(basename)
        ext = ext.lower()
        prefix = self.s3_prefix
        key_sections = [
            prefix,
            self.website.short_id,
            self.file_id if self.is_video() else None,
            f"{basename}{ext}",
        ]
        s3_key = "/".join([section for section in key_sections if section])
        drive_file_exists = DriveFile.objects.filter(s3_key=s3_key).exists()
        if not drive_file_exists:
            return s3_key
        drive_file_qset = DriveFile.objects.exclude(s3_key=s3_key)
        return find_available_name(
            drive_file_qset,
            os.path.splitext(s3_key)[0],
            "s3_key",
            max_length=4096,
            extension=ext,
        )

    @property
    def s3_prefix(self):
        """Return the S3 prefix that should be used for the file"""
        return (
            settings.DRIVE_S3_UPLOAD_PREFIX
            if self.is_video()
            else self.website.starter.config.get("root-url-path").rstrip("/")
        )

    def __str__(self):
        return f"'{self.name}' ({self.drive_path} {self.status} {self.file_id})"
