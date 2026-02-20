"""Signals for websites"""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from websites.constants import (
    CONTENT_TYPE_COURSE_LIST,
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    WEBSITE_CONTENT_LEFTNAV,
    WEBSITE_PAGES_PATH,
)
from websites.models import Website, WebsiteContent
from websites.permissions import setup_website_groups_permissions
from websites.utils import populate_course_list_text_ids


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
def populate_course_list_text_ids_on_save(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Auto-populate text_id fields in course-list entries when saving.
    """
    if instance.type == CONTENT_TYPE_COURSE_LIST and populate_course_list_text_ids(
        instance
    ):
        instance.metadata = instance.metadata


@receiver(pre_save, sender=WebsiteContent)
def update_navmenu_on_page_url_change(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Update navmenu when the URL of a page changes.
    """

    if instance.type != CONTENT_TYPE_PAGE:
        return

    try:
        prev_instance = WebsiteContent.objects.get(pk=instance.pk)
        if prev_instance.filename == instance.filename:
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
