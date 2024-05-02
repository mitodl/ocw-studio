"""Signals for content syncing"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from content_sync import api
from websites.models import WebsiteContent


@receiver(
    post_save,
    sender=WebsiteContent,
    dispatch_uid="sync_state_website_content_upsert",
)
def upsert_content_sync_state(
    sender,  # noqa: ARG001
    instance,
    created,  # noqa: ARG001
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """Create/update the sync state"""
    api.upsert_content_sync_state(instance)
