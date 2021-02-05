"""Signals for websites"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from websites import constants
from websites.permissions import create_website_groups, assign_object_permissions
from websites.models import Website


@receiver(
    post_save,
    sender=Website,
    dispatch_uid="website_post_save",
)
@transaction.atomic
def handle_website_save(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    """
    Add website-specific groups with appropriate permissions when a website is created
    """
    if created:
        create_website_groups(instance)
        if instance.owner:
            assign_object_permissions(
                instance.owner, instance, constants.PERMISSIONS_ADMIN
            )
