""" Models for gdrive_sync """
import os
from functools import reduce
from typing import Iterable

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from mitol.common.models import TimestampedModel

from gdrive_sync.constants import (
    DRIVE_API_RESOURCES,
    DRIVE_FOLDER_VIDEOS_FINAL,
    DriveFileStatus,
)
from videos.models import Video
from websites.api import find_available_name
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.utils import resource_reference_field_filter


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
    sync_error = models.TextField(null=True, blank=True)
    sync_dt = models.DateTimeField(null=True, blank=True)

    def update_status(self, status):
        """ Update the DriveFile status"""
        self.status = status
        self.save()

    def is_video(self):
        """Return True if is is in the video folder"""
        return self.mime_type.lower().startswith(
            "video/"
        ) and DRIVE_FOLDER_VIDEOS_FINAL in self.drive_path.split("/")

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
            self.website.name,
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

    def get_content_dependencies(self) -> Iterable[WebsiteContent]:
        """
        Find and return WebsiteContent that make use of this file through
        `self.resource`.

        Returns:
            Iterable[WebsiteContent]: A list of WebsiteContent that makes use of this file
                directly/indirectly.
        """
        if self.resource is None:
            return []

        website = self.website
        resource_id = self.resource.text_id

        filters = []

        for is_website_config, config_item in WebsiteStarter.iter_all_config_items(
            website
        ):
            for config_field in config_item.iter_fields(
                only_cross_site=not is_website_config
            ):
                field = config_field.field
                field_q = resource_reference_field_filter(field, resource_id, website)

                if field_q is None:
                    continue

                q = Q(type=config_item.name) & field_q

                if not field.get("cross_site", False):
                    q = Q(website=website) & q

                filters.append(q)

        if not filters:
            return []

        query = reduce(lambda x, y: x | y, filters)
        dependencies = WebsiteContent.objects.filter(query)

        return list(dependencies)

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
