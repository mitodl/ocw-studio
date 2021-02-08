""" permissions for websites """
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from guardian.shortcuts import assign_perm, get_perms
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission, SAFE_METHODS

from users.models import User
from websites import constants
from websites.models import Website


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
        current_perms = set(get_perms(group_or_user, website))
    elif isinstance(group_or_user, Group):
        current_perms = {perm.codename for perm in group_or_user.permissions.all()}
    elif isinstance(group_or_user, User):
        current_perms = {
            perm.codename for perm in Permission.objects.filter(user=group_or_user)
        }
    else:
        raise TypeError("Permissions must be assigned to a user or group")
    if not {perm.replace("websites.", "") for perm in perms}.difference(current_perms):
        return False
    for perm in perms:
        try:
            if website:
                assign_perm(perm, group_or_user, website)
            else:
                assign_perm(perm, group_or_user)
        except Permission.DoesNotExist as err:
            raise Permission.DoesNotExist(f"Permission '{perm}' not found") from err
    return True


@transaction.atomic
def create_website_groups(website):
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
        name=f"{constants.ADMIN_GROUP}{website.uuid.hex}"
    )
    if admin_created:
        groups_created += 1
    editor_group, editor_created = Group.objects.get_or_create(
        name=f"{constants.EDITOR_GROUP}{website.uuid.hex}"
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

    global_perms = [constants.PERMISSION_ADD]
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


def is_global_admin(user):
    """
    Determine if the user is a global administrator or superuser

    Args:
        user (users.models.User): The user to check

    Returns:
        bool: True if a superuser or member of the global admin group

    """
    return user.is_superuser or user.groups.filter(name=constants.GLOBAL_ADMIN).exists()


def is_site_admin(user, website):
    """
    Determine if the user is effectively an admin for a site

    Args:
        user (users.models.User): The user to check
        website (Website): The website to check

    Returns:
        bool: True if user is an admin for the site
    """
    return (
        is_global_admin(user)
        or website.owner == user
        or user.groups.filter(name=website.admin_group).exists()
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

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            # Only global editors and admins can create new Websites
            return request.user.has_perm(constants.PERMISSION_ADD)
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in SAFE_METHODS:
            return check_perm(user, constants.PERMISSION_VIEW, obj)
        elif request.method == "PATCH":
            return check_perm(user, constants.PERMISSION_EDIT, obj)
        return False


class HasWebsiteContentPermission(BasePermission):
    """Permission to view/modify WebsiteContent objects"""

    def has_permission(self, request, view):
        # The parent website should be included in the kwargs via DRF extensions nested view
        website = get_object_or_404(
            Website, uuid=view.kwargs.get("parent_lookup_website", None)
        )
        if request.method in SAFE_METHODS:
            return check_perm(request.user, constants.PERMISSION_VIEW, website)
        else:
            return check_perm(request.user, constants.PERMISSION_EDIT_CONTENT, website)

    def has_object_permission(self, request, view, obj):
        user = request.user
        website = obj.website
        if request.method in SAFE_METHODS:
            return check_perm(user, constants.PERMISSION_VIEW, website)
        if request.method == "PATCH":
            return check_perm(user, constants.PERMISSION_EDIT_CONTENT, website)
        if request.method == "DELETE":
            return is_site_admin(user, website) or obj.owner == user
        return False


class HasWebsitePublishPermission(BasePermission):
    """Permission to publish or unpublish a website"""

    def has_object_permission(self, request, view, obj):
        return check_perm(request.user, constants.PERMISSION_PUBLISH, obj)


class HasWebsiteCollaborationPermission(BasePermission):
    """Permission to add or remove a website admin/editor"""

    def has_object_permission(self, request, view, obj):
        return check_perm(request.user, constants.PERMISSION_COLLABORATE, obj)


class HasWebsitePreviewPermission(BasePermission):
    """Permission to preview a website"""

    def has_object_permission(self, request, view, obj):
        return check_perm(request.user, constants.PERMISSION_PREVIEW, obj)
