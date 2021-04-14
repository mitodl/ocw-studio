"""Signals for content syncing"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from content_sync import api
from websites.models import WebsiteContent


@receiver(
    post_save,
    sender=WebsiteContent,
    dispatch_uid="website_content_create_sync_state",
)
def upsert_content_sync_state(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    """ Create/update the sync state """
    api.upsert_content_sync_state(instance)
