"""Signals for websites"""

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from safedelete.signals import post_softdelete

from content_sync.apis.github import GIT_DATA_FILEPATH
from content_sync.decorators import is_sync_enabled
from content_sync.models import ContentSyncState
from content_sync.tasks import delete_orphaned_content_file
from content_sync.utils import get_destination_filepath
from websites.api import unlink_deleted_resource_from_videos
from websites.constants import (
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    WEBSITE_CONTENT_LEFTNAV,
    WEBSITE_PAGES_PATH,
)
from websites.models import Website, WebsiteContent
from websites.permissions import setup_website_groups_permissions
from websites.site_config_api import SiteConfig

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
    pre_delete,
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

    Runs on pre_delete, not post_delete, so the content's ContentSyncState
    (cascade-deleted along with it) can still be read here to recover the
    path it was last actually synced to. Recomputing the path fresh from the
    row's current fields would target the wrong file for content that was
    renamed but never resynced before being hard-deleted.

    The actual backend call is deferred via transaction.on_commit into a
    background task rather than made inline: inline, it would run inside
    the same transaction as the delete (so a later rollback couldn't undo an
    already-made GitHub API call), and for a bulk hard-delete it would turn
    every row into a blocking, synchronous network request even though the
    sanctioned bulk-delete flows already remove their own backend files.
    """
    website = instance.website
    filepath = None
    try:
        sync_state = instance.content_sync_state
    except ContentSyncState.DoesNotExist:
        sync_state = None
    if sync_state and sync_state.data:
        filepath = sync_state.data.get(GIT_DATA_FILEPATH)
    if not filepath:
        site_config = SiteConfig(website.starter.config)
        filepath = get_destination_filepath(instance, site_config)
    if not filepath:
        return

    website_pk = website.pk
    updated_by_pk = instance.updated_by_id

    transaction.on_commit(
        lambda: delete_orphaned_content_file.delay(
            str(website_pk), filepath, updated_by_pk
        )
    )
