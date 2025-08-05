"""Signals for websites"""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from websites.constants import (
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    WEBSITE_CONTENT_LEFTNAV,
    WEBSITE_PAGES_PATH,
)
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
def update_navmenu_on_title_change(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Update navmenu when the title of a page changes.
    """

    if instance.type != CONTENT_TYPE_PAGE:
        return

    try:
        prev_instance = WebsiteContent.objects.get(pk=instance.pk)
        if prev_instance.title == instance.title:
            return
    except WebsiteContent.DoesNotExist:
        return

    new_filename = slugify(instance.title)
    if instance.filename == new_filename:
        try:
            navmenu = WebsiteContent.objects.get(
                website=instance.website,
                type=CONTENT_TYPE_NAVMENU,
            )
            menu_items = navmenu.metadata.get(WEBSITE_CONTENT_LEFTNAV, [])
            navmenu_updated = False
            for item in menu_items:
                if item.get("identifier") == instance.text_id:
                    item["pageRef"] = f"/{WEBSITE_PAGES_PATH}/{new_filename}"
                    item["name"] = instance.title
                    navmenu_updated = True
            if navmenu_updated:
                navmenu.metadata[WEBSITE_CONTENT_LEFTNAV] = menu_items
                navmenu.save(update_fields=["metadata"])
        except WebsiteContent.DoesNotExist:
            pass
