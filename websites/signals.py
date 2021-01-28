"""Signals for websites"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from websites.models import Website
from websites.permissions import setup_website_groups_permissions


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
        setup_website_groups_permissions(instance)
