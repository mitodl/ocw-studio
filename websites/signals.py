"""Signals for websites"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from safedelete.signals import post_softdelete

from content_sync.api import get_sync_backend
from content_sync.decorators import is_sync_enabled
from websites.api import unlink_deleted_resource_from_videos
from websites.constants import (
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    WEBSITE_CONTENT_LEFTNAV,
    WEBSITE_PAGES_PATH,
)
from websites.models import Website, WebsiteContent
from websites.permissions import setup_website_groups_permissions

log = logging.getLogger(__name__)


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


@receiver(post_softdelete, sender=WebsiteContent)
def unlink_deleted_resource_on_softdelete(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    When a resource referenced by a video (as a caption/transcript) is
    deleted, remove it from that video's relation content list.
    """
    if not instance.referencing_content.exists():
        return
    unlink_deleted_resource_from_videos(instance)


@receiver(
    post_delete,
    sender=WebsiteContent,
    dispatch_uid="delete_content_from_backend_on_hard_delete",
)
@is_sync_enabled
def delete_content_from_backend_on_hard_delete(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Safety net for hard-deletes that bypass the normal managed sync flow
    (e.g. a management command or shell session calling
    `.delete(force_policy=HARD_DELETE)` directly): removes the content's
    file from the git backend so it doesn't stay orphaned forever.

    Hard-deletes that already go through the normal flow (GithubBackend's
    delete_content_in_backend / sync_all_content_to_db /
    upsert_content_files_for_user) have already removed the backend file by
    the time this fires; the resulting redundant call is a cheap no-op
    because delete_content_file treats an already-missing file as success
    rather than an error.
    """
    website = instance.website
    try:
        backend = get_sync_backend(website)
        backend.api.delete_content_file(instance)
    except Exception:  # pylint:disable=broad-except
        log.exception(
            "Failed to delete backend file for hard-deleted content %s (%s)",
            instance.text_id,
            website.name,
        )
