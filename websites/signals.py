"""Signals for websites"""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from websites.models import Website, WebsiteContent
from websites.permissions import setup_website_groups_permissions


@receiver(
    post_save,
    sender=Website,
    dispatch_uid="website_post_save",
)
@transaction.atomic
def handle_website_save(
    sender,  # noqa: ARG001
    instance,
    created,
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Add website-specific groups with appropriate permissions when a website is created
    """
    if created:
        setup_website_groups_permissions(instance)


@receiver(pre_save, sender=WebsiteContent)
def update_page_url_on_title_change(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """Update page URL when title changes for page content"""

    if instance.is_page_content and instance.title:
        new_filename = slugify(instance.title)
        cur_filename = WebsiteContent.objects.filter(
            website=instance.website,
            dirpath=instance.dirpath,
            filename=new_filename,
            is_page_content=True,
        ).exclude(pk=instance.pk)

        if not cur_filename.exists():
            instance.filename = new_filename
