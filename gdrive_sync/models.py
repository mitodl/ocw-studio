""" Models for gdrive_sync """
from django.db.models import SET_NULL, CharField, DateTimeField, ForeignKey, URLField
from mitol.common.models import TimestampedModel

from gdrive_sync.constants import DRIVE_API_RESOURCES, DriveFileStatus
from websites.models import Website


class DriveApiQueryTracker(TimestampedModel):
    """ Object for tracking the last google drive api call for a certain resource"""

    api_call = CharField(
        null=False,
        blank=False,
        max_length=128,
        unique=True,
        choices=zip(DRIVE_API_RESOURCES, DRIVE_API_RESOURCES),
    )
    last_page = CharField(max_length=2048, null=True, blank=True)
    last_dt = DateTimeField(null=True, blank=True)


class DriveFile(TimestampedModel):
    """ Model representation of a Google drive file"""

    file_id = CharField(primary_key=True, null=False, blank=False, max_length=128)
    name = CharField(null=False, blank=False, max_length=32767)
    mime_type = CharField(max_length=256, null=False, blank=False)
    checksum = CharField(null=False, blank=False, max_length=32)
    s3_key = CharField(max_length=32767, null=True, blank=True)
    download_link = URLField(null=False, blank=False)
    status = CharField(
        null=False,
        default=DriveFileStatus.CREATED,
        max_length=50,
    )
    modified_time = DateTimeField(null=True, blank=True)
    created_time = DateTimeField(null=True, blank=True)
    website = ForeignKey(Website, null=True, on_delete=SET_NULL)
    drive_path = CharField(null=False, max_length=2048)

    def update_status(self, status):
        """ Update the DriveFile status"""
        self.status = status
        self.save()
