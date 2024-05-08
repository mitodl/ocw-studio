"""permissions for websites"""
import logging

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from guardian.shortcuts import assign_perm, get_perms
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.models import User
from websites import constants
from websites.constants import ADMIN_ONLY_CONTENT
from websites.models import Website
from websites.utils import permissions_group_name_for_role

log = logging.getLogger(__name__)


def assign_website_permissions(group_or_user, perms, website=None):
    """
    Assign appropriate permissions to a website admin group

    Args:
        group_or_user (Group or User): the group/user to add permissions to
        website (Object): The object that the permissions are for (typically Website)
        perms (list of str): The permissions to be assigned

    Returns:
        bool: True if any permissions were added, False otherwise
    """
    if website:
        current_perm_codenames = set(get_perms(group_or_user, website))
    elif isinstance(group_or_user, Group):
        current_perm_codenames = {
            perm.codename for perm in group_or_user.permissions.all()
        }
    elif isinstance(group_or_user, User):
        current_perm_codenames = {
            perm.codename for perm in Permission.objects.filter(user=group_or_user)
        }
    else:
        msg = "Permissions must be assigned to a user or group"
        raise TypeError(msg)
    added_perm_codenames = {perm.replace("websites.", "") for perm in perms}
    if not added_perm_codenames.difference(current_perm_codenames):
        return False
    for perm in perms:
        try:
            if website:
                assign_perm(perm, group_or_user, website)
            else:
                assign_perm(perm, group_or_user)
        except Permission.DoesNotExist as err:  # noqa: PERF203
            msg = f"Permission '{perm}' not found"
            raise Permission.DoesNotExist(msg) from err
    return True


@transaction.atomic
def setup_website_groups_permissions(website):
    """
    Create groups and assign permissions for a website

    Args:
        website (Website): The website that the permissions are for

    Returns:
        list (int, int, bool): # groups created, # groups updated, owner updated
    """
    groups_created = 0
    groups_updated = 0
    owner_updated = False

    admin_group, admin_created = Group.objects.get_or_create(
        name=permissions_group_name_for_role(constants.ROLE_ADMINISTRATOR, website)
    )
    if admin_created:
        groups_created += 1
    editor_group, editor_created = Group.objects.get_or_create(
        name=permissions_group_name_for_role(constants.ROLE_EDITOR, website)
    )
    if editor_created:
        groups_created += 1

    if (
        assign_website_permissions(
            admin_group, constants.PERMISSIONS_ADMIN, website=website
        )
        and not admin_created
    ):
        groups_updated += 1

    if (
        assign_website_permissions(
            editor_group, constants.PERMISSIONS_EDITOR, website=website
        )
        and not editor_created
    ):
        groups_updated += 1

    if website.owner:
        owner_updated = assign_website_permissions(
            website.owner, constants.PERMISSIONS_ADMIN, website=website
        )

    return groups_created, groups_updated, owner_updated


@transaction.atomic
def create_global_groups():
    """
    Create the global groups for website permissions

    Args:
        website (Website): The website that the permissions are for

    Returns:
        list (int, int): # groups created, # groups updated
    """
    groups_created = 0
    groups_updated = 0

    admin_group, admin_created = Group.objects.get_or_create(
        name=constants.GLOBAL_ADMIN
    )
    if admin_created:
        groups_created += 1
    author_group, author_created = Group.objects.get_or_create(
        name=constants.GLOBAL_AUTHOR
    )
    if author_created:
        groups_created += 1

    global_perms = constants.PERMISSIONS_GLOBAL_AUTHOR
    if (
        assign_website_permissions(
            admin_group, global_perms + constants.PERMISSIONS_ADMIN
        )
        and not admin_created
    ):
        groups_updated += 1
    if assign_website_permissions(author_group, global_perms) and not author_created:
        groups_updated += 1

    return groups_created, groups_updated


def is_global_admin(user, group_names=None):
    """
    Determine if the user is a global administrator or superuser

    Args:
        user (users.models.User): The user to check
        group_names (set of str): an optional set of group names to check against

    Returns:
        bool: True if a superuser or member of the global admin group

    """
    if user.is_superuser:
        return True
    group_names = group_names or set(user.groups.values_list("name", flat=True))
    return constants.GLOBAL_ADMIN in group_names


def is_site_admin(user, website):
    """
    Determine if the user is effectively an admin for a site

    Args:
        user (users.models.User): The user to check
        website (Website): The website to check

    Returns:
        bool: True if user is an admin for the site
    """
    group_names = set(user.groups.values_list("name", flat=True))
    return (
        is_global_admin(user, group_names=group_names)
        or website.owner == user
        or permissions_group_name_for_role(constants.ROLE_ADMINISTRATOR, website)
        in group_names
    )


def check_perm(user, permission, website):
    """
    Determine if the user has a global or website-specific permission

    Args:
        user (users.models.User): The user to check
        permission (str): The permission to check
        website (Website): The website to check

    """
    return user.has_perm(permission, website) or user.has_perm(permission)


class HasWebsitePermission(BasePermission):
    """Permission to view/modify/create Website objects"""

    def has_permission(self, request, view):  # noqa: ARG002
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            # Only global editors and admins can create new Websites
            return request.user.has_perm(constants.PERMISSION_ADD)
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):  # noqa: ARG002
        user = request.user
        if request.method in SAFE_METHODS:
            return check_perm(user, constants.PERMISSION_VIEW, obj)
        elif request.method == "PATCH":
            return check_perm(user, constants.PERMISSION_EDIT, obj)
        return False


class HasWebsiteContentPermission(BasePermission):
    """Permission to view/modify WebsiteContent objects"""

    def has_permission(self, request, view):
        # The parent website should be included in the kwargs via DRF extensions nested view  # noqa: E501
        website = get_object_or_404(
            Website, name=view.kwargs.get("parent_lookup_website", None)
        )
        if request.method in SAFE_METHODS:
            # Give permission to any logged in user, to facilitate content relations between different sites.  # noqa: E501
            # In particular, to allow instructor relations from ocw-www in site metadata.  # noqa: E501
            return bool(request.user and request.user.is_authenticated)
        if request.data and request.data.get("type") in ADMIN_ONLY_CONTENT:
            return is_site_admin(request.user, website)
        return check_perm(request.user, constants.PERMISSION_EDIT_CONTENT, website)

    def has_object_permission(self, request, view, obj):  # noqa: ARG002
        user = request.user
        website = obj.website
        if request.method in SAFE_METHODS:
            return check_perm(user, constants.PERMISSION_VIEW, website)
        if obj.type in ADMIN_ONLY_CONTENT:
            return is_site_admin(user, website)
        if request.method == "PATCH":
            return check_perm(user, constants.PERMISSION_EDIT_CONTENT, website)
        if request.method == "DELETE":
            return is_site_admin(user, website) or obj.owner == user
        return False


class HasWebsitePublishPermission(BasePermission):
    """Permission to publish or unpublish a website"""

    def has_object_permission(self, request, view, obj):  # noqa: ARG002
        return check_perm(request.user, constants.PERMISSION_PUBLISH, obj)


class HasWebsiteCollaborationPermission(BasePermission):
    """Permission to add or remove a website admin/editor"""

    def has_permission(self, request, view):
        website = get_object_or_404(
            Website, name=view.kwargs.get("parent_lookup_website", None)
        )
        return check_perm(request.user, constants.PERMISSION_COLLABORATE, website)

    def has_object_permission(self, request, view, obj):
        website = get_object_or_404(
            Website, name=view.kwargs.get("parent_lookup_website", None)
        )
        if request.method not in SAFE_METHODS and (
            website.owner == obj or is_global_admin(obj)
        ):
            return False
        # Anyone not allowed to do this will already have been stopped by has_permission above  # noqa: E501
        return True


class HasWebsitePreviewPermission(BasePermission):
    """Permission to preview a website"""

    def has_object_permission(self, request, view, obj):  # noqa: ARG002
        return check_perm(request.user, constants.PERMISSION_PREVIEW, obj)


class BearerTokenPermission(BasePermission):
    """Restrict access to api endpoints via access token"""

    def has_permission(self, request, view):  # noqa: ARG002
        if not settings.API_BEARER_TOKEN:
            log.error("API_BEARER_TOKEN not set")
            return False
        header = request.headers.get("Authorization", "")
        if header and header.startswith("Bearer "):
            token = header[len("Bearer ") :]
            return token == settings.API_BEARER_TOKEN
        return False
