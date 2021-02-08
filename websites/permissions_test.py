""" Tests for websites permissions"""
import pytest
from django.contrib.auth.models import Permission, Group

from users.factories import UserFactory
from websites import permissions, constants
from websites.factories import WebsiteFactory
from websites.permissions import (
    assign_object_permissions,
    create_global_groups,
    create_website_groups,
)

pytestmark = pytest.mark.django_db


def test_is_global_admin(permission_groups):
    """ Global admin users should be identified correctly """
    superuser = UserFactory.create(is_superuser=True)
    for user in [permission_groups.global_admin, superuser]:
        assert permissions.is_global_admin(user) is True
    for user in [
        permission_groups.global_author,
        permission_groups.site_admin,
        permission_groups.site_editor,
    ]:
        assert permissions.is_global_admin(user) is False


def test_is_site_admin(permission_groups):
    """ Any website-specific or global admin users should be identified correctly """
    website = permission_groups.websites[0]
    superuser = UserFactory.create(is_superuser=True)
    for user in [
        permission_groups.global_admin,
        permission_groups.site_admin,
        website.owner,
        superuser,
    ]:
        assert permissions.is_site_admin(user, website) is True
    for user in [
        permission_groups.global_author,
        permission_groups.site_editor,
    ]:
        assert permissions.is_site_admin(user, website) is False


@pytest.mark.parametrize("method", ["GET", "PATCH"])
def test_can_view_edit_preview_website(mocker, permission_groups, method):
    """
    Test that admins/owners are allowed to view/edit/preview websites
    """
    website_0_allowed_users = [
        permission_groups.global_admin,
        permission_groups.site_admin,
        permission_groups.websites[0].owner,
    ]
    website_1_allowed_users = [
        permission_groups.global_admin,
        permission_groups.websites[0].owner,
    ]

    for user in [
        permission_groups.global_admin,
        permission_groups.global_author,
        permission_groups.site_admin,
        permission_groups.websites[0].owner,
    ]:
        request = mocker.Mock(user=user, method=method)
        assert permissions.HasWebsitePermission().has_permission(
            request, mocker.Mock()
        ) is (method == "GET")
        for permission_class in (
            permissions.HasWebsitePermission(),
            permissions.HasWebsitePreviewPermission(),
        ):
            assert permission_class.has_object_permission(
                request, mocker.Mock(), permission_groups.websites[0]
            ) is (user in website_0_allowed_users)
            assert permission_class.has_object_permission(
                request, mocker.Mock(), permission_groups.websites[1]
            ) is (user in website_1_allowed_users)


@pytest.mark.parametrize("method,has_perm", [["PATCH", False], ["GET", True]])
def test_editor_can_view_not_edit_website(mocker, permission_groups, method, has_perm):
    """A site editor should be able to view but not edit the website"""
    site_editor = permission_groups.site_editor
    website = permission_groups.websites[0]

    assert (
        permissions.HasWebsitePermission().has_object_permission(
            mocker.Mock(user=site_editor, method=method), mocker.Mock(), website
        )
        is has_perm
    )


def test_editor_can_preview_website(mocker, permission_groups):
    """A site editor should be able to preview the website"""
    site_editor = permission_groups.site_editor
    website = permission_groups.websites[0]
    assert (
        permissions.HasWebsitePreviewPermission().has_object_permission(
            mocker.Mock(user=site_editor, method="PATCH"), mocker.Mock(), website
        )
        is True
    )


def test_can_create_website(mocker, permission_groups):
    """ Only global admins and global authors can create new websites """
    for user in [
        permission_groups.global_admin,
        permission_groups.global_author,
    ]:
        request = mocker.Mock(user=user, method="POST")
        assert (
            permissions.HasWebsitePermission().has_permission(request, mocker.Mock())
            is True
        )

    for user in [
        permission_groups.site_admin,
        permission_groups.site_editor,
        permission_groups.websites[0].owner,
    ]:
        request = mocker.Mock(user=user, method="POST")
        assert (
            permissions.HasWebsitePermission().has_permission(request, mocker.Mock())
            is False
        )


def test_cannot_delete_website(mocker, permission_groups):
    """ No one can delete websites """
    for website in permission_groups.websites:
        for user in [
            permission_groups.global_admin,
            permission_groups.global_author,
            permission_groups.site_admin,
            permission_groups.site_editor,
            website.owner,
        ]:
            request = mocker.Mock(user=user, method="DELETE")
            assert (
                permissions.HasWebsitePermission().has_object_permission(
                    request, mocker.Mock(), website
                )
                is False
            )


@pytest.mark.parametrize("method", ["GET", "PATCH"])
def test_author_cannot_view_edit_other_website(mocker, permission_groups, method):
    """A global author should not be able to view other authors' websites"""
    global_author = permission_groups.global_author
    website_other = permission_groups.websites[0]
    website_own = WebsiteFactory.create(owner=global_author)

    for [website, has_perm] in ([website_other, False], [website_own, True]):
        assert (
            permissions.HasWebsitePermission().has_object_permission(
                mocker.Mock(user=global_author, method=method), mocker.Mock(), website
            )
            is has_perm
        )


def test_can_publish_website(mocker, permission_groups):
    """ Test that only appropriate users can publish a website """
    website = permission_groups.websites[0]
    for [user, has_perm] in [
        [permission_groups.global_admin, True],
        [permission_groups.site_admin, True],
        [permission_groups.websites[0].owner, True],
        [permission_groups.global_author, False],
        [permission_groups.site_editor, False],
    ]:
        request = mocker.Mock(user=user)
        assert (
            permissions.HasWebsitePublishPermission().has_object_permission(
                request, mocker.Mock(), website
            )
            is has_perm
        )


@pytest.mark.parametrize("method", ["GET", "PATCH", "POST", "DELETE"])
def test_can_change_collaborators_website(mocker, permission_groups, method):
    """ Test that only appropriate users can add/remove website collaborators"""
    website = permission_groups.websites[0]
    for [user, has_perm] in [
        [permission_groups.global_admin, True],
        [permission_groups.site_admin, True],
        [permission_groups.websites[0].owner, True],
        [permission_groups.global_author, False],
        [permission_groups.site_editor, False],
    ]:
        request = mocker.Mock(user=user, method=method)
        assert (
            permissions.HasWebsiteCollaborationPermission().has_object_permission(
                request, mocker.Mock(), website
            )
            is has_perm
        )


def test_can_create_website_content(mocker, permission_groups):
    """ Verify that website admins and editors can create content"""
    website = permission_groups.websites[0]

    # This assumes the WebsiteContent API view will be nested via DRF extensions
    view = mocker.Mock(kwargs={"parent_lookup_website": str(website.uuid)})

    # All site editors and admins should be able to view or create content for that site
    for user in [
        permission_groups.global_admin,
        permission_groups.site_admin,
        permission_groups.site_editor,
        website.owner,
    ]:
        assert (
            permissions.HasWebsiteContentPermission().has_permission(
                mocker.Mock(user=user, method="POST"), view
            )
            is True
        )

    # A website admin cannot create content for another website, a global admin can
    view = mocker.Mock(
        kwargs={"parent_lookup_website": str(permission_groups.websites[1].uuid)}
    )
    for [user, has_perm] in [
        [permission_groups.site_admin, False],
        [permission_groups.global_admin, True],
        [permission_groups.global_author, False],
    ]:
        assert (
            permissions.HasWebsiteContentPermission().has_permission(
                mocker.Mock(user=user, method="POST"), view
            )
            is has_perm
        )


def test_can_view_edit_website_content(mocker, permission_groups):
    """
    Test that appropriate users are allowed to view, create, edit WebsiteContent objects
    """
    website = permission_groups.websites[0]

    # This assumes the WebsiteContent API view will be nested via DRF extensions
    view = mocker.Mock(kwargs={"parent_lookup_website": str(website.uuid)})

    for [user, has_perm] in [
        [permission_groups.global_admin, True],
        [permission_groups.global_author, False],
        [permission_groups.site_admin, True],
        [permission_groups.site_editor, True],
        [website.owner, True],
    ]:
        for method in ["GET", "POST"]:
            assert (
                permissions.HasWebsiteContentPermission().has_permission(
                    mocker.Mock(user=user, method=method), view
                )
                is has_perm
            )

        for method in ["GET", "PATCH"]:
            for content in [
                permission_groups.owner_content,
                permission_groups.editor_content,
            ]:
                assert (
                    permissions.HasWebsiteContentPermission().has_object_permission(
                        mocker.Mock(user=user, method=method), view, content
                    )
                    is has_perm
                )


def test_editors_can_delete_own_website_content(mocker, permission_groups):
    """A website editor can only delete their own content"""
    for [content, has_perm] in [
        [permission_groups.owner_content, False],
        [permission_groups.editor_content, True],
    ]:
        assert (
            permissions.HasWebsiteContentPermission().has_object_permission(
                mocker.Mock(user=permission_groups.site_editor, method="DELETE"),
                mocker.Mock(),
                content,
            )
            is has_perm
        )


def test_admins_can_delete_any_website_content(mocker, permission_groups):
    """Admins, website creators should be able to delete any content"""
    website = permission_groups.websites[0]
    for content in [permission_groups.editor_content, permission_groups.owner_content]:
        for user in [
            permission_groups.global_admin,
            permission_groups.site_admin,
            website.owner,
        ]:
            assert (
                permissions.HasWebsiteContentPermission().has_object_permission(
                    mocker.Mock(user=user, method="DELETE"), mocker.Mock(), content
                )
                is True
            )


def test_create_website_groups():
    """ Permissions should be assigned as expected """
    owner, admin, editor = UserFactory.create_batch(3)
    website = WebsiteFactory.create(owner=owner)
    create_website_groups(website)
    admin.groups.add(website.admin_group)
    editor.groups.add(website.editor_group)
    for permission in constants.PERMISSIONS_EDITOR:
        assert editor.has_perm(permission, website) is True
    for permission in constants.PERMISSIONS_ADMIN:
        for user in [owner, admin]:
            assert user.has_perm(permission, website) is True

    for permission in [constants.PERMISSION_PUBLISH, constants.PERMISSION_COLLABORATE]:
        assert editor.has_perm(permission, website) is False


def test_assign_group_permissions_error():
    """ An exception should be raised if an invalid permission is used"""
    website = WebsiteFactory.create()
    bad_perm = "fake_perm_website"
    with pytest.raises(Permission.DoesNotExist) as exc:
        assign_object_permissions(website.editor_group, website, [bad_perm])
    assert exc.value.args == (f"Permission '{bad_perm}' not found",)


def test_create_global_groups():
    """Global permission groups should be created and have appropriate permissions"""

    # Delete them so they can be recreated
    Group.objects.get(name=constants.GLOBAL_ADMIN).delete()
    Group.objects.get(name=constants.GLOBAL_AUTHOR).delete()

    admin, author = UserFactory.create_batch(2)
    create_global_groups()
    admin_group = Group.objects.get(name=constants.GLOBAL_ADMIN)
    admin.groups.add(admin_group)
    author_group = Group.objects.get(name=constants.GLOBAL_AUTHOR)
    author.groups.add(author_group)
    for permission in constants.PERMISSIONS_ADMIN:
        assert admin.has_perm(permission) is True
    for permission in constants.PERMISSIONS_EDITOR:
        assert author.has_perm(permission) is False
    assert author.has_perm(constants.PERMISSION_ADD) is True
