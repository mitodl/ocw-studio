"""Signals for grdive_sync"""

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from gdrive_sync.models import DriveFile
from videos.tasks import delete_s3_objects


@receiver(pre_delete, sender=DriveFile)
def delete_from_s3(sender, **kwargs):  # pylint:disable=unused-argument  # noqa: ARG001
    """
    Delete the drive file from S3
    """
    drive_file = kwargs["instance"]
    delete_s3_objects.delay(drive_file.s3_key)
