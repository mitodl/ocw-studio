""" permissions for websites """
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from guardian.shortcuts import assign_perm
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission, SAFE_METHODS

from websites import constants
from websites.models import Website


def assign_object_permissions(group_or_user, website, perms):
    """
    Assign appropriate permissions to a website admin group

    Args:
        group_or_user (Group or User): the group/user to add permissions to
        website (Website): The website that the permissions are for
        perms (list of str): The permissions to be assigned
    """
    for perm in perms:
        try:
            assign_perm(perm, group_or_user, website)
        except Permission.DoesNotExist as err:
            raise Permission.DoesNotExist(f"Perm {perm} not found") from err


@transaction.atomic
def create_website_groups(website):
    """
    Create groups and assign permissions for a website

    Args:
        website (Website): The website that the permissions are for
    """
    admin_group, _ = Group.objects.get_or_create(
        name=f"{constants.ADMIN_GROUP}{website.uuid.hex}"
    )
    editor_group, _ = Group.objects.get_or_create(
        name=f"{constants.EDITOR_GROUP}{website.uuid.hex}"
    )
    assign_object_permissions(admin_group, website, constants.PERMISSIONS_ADMIN)
    assign_object_permissions(editor_group, website, constants.PERMISSIONS_EDITOR)


@transaction.atomic
def create_global_groups():
    """Create the global groups for website permissions"""
    admin_group, _ = Group.objects.get_or_create(name=constants.GLOBAL_ADMIN)
    author_group, _ = Group.objects.get_or_create(name=constants.GLOBAL_AUTHOR)
    for perm in constants.PERMISSIONS_ADMIN:
        assign_perm(perm, admin_group)
    assign_perm(constants.PERMISSION_ADD, admin_group)
    assign_perm(constants.PERMISSION_ADD, author_group)


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
        if request.method == "POST":
            # Only global editors and admins can create new Websites
            return request.user.has_perm(constants.PERMISSION_ADD)
        return True

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
