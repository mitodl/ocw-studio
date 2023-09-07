"""Tests for websites collaborator views"""

import pytest
from django.urls import reverse

from users.factories import UserFactory
from users.models import User
from websites import constants

# pylint:disable=redefined-outer-name

pytestmark = pytest.mark.django_db


def test_websites_collaborators_endpoint_list_permissions(
    drf_client, permission_groups
):
    """Only admins should see collaborators list"""
    website = permission_groups.websites[0]
    expected_results = sorted(
        [
            {
                "user_id": permission_groups.site_admin.id,
                "email": permission_groups.site_admin.email,
                "name": permission_groups.site_admin.name,
                "role": constants.ROLE_ADMINISTRATOR,
            },
            {
                "user_id": permission_groups.site_editor.id,
                "email": permission_groups.site_editor.email,
                "name": permission_groups.site_editor.name,
                "role": constants.ROLE_EDITOR,
            },
            {
                "user_id": permission_groups.global_admin.id,
                "email": permission_groups.global_admin.email,
                "name": permission_groups.global_admin.name,
                "role": constants.GLOBAL_ADMIN,
            },
            {
                "user_id": website.owner.id,
                "email": website.owner.email,
                "name": website.owner.name,
                "role": constants.ROLE_OWNER,
            },
        ],
        key=lambda user: (user["name"], user["user_id"]),
    )
    for user in [
        permission_groups.global_admin,
        permission_groups.site_admin,
        website.owner,
    ]:
        drf_client.force_login(user)
        resp = drf_client.get(
            reverse(
                "websites_collaborators_api-list",
                kwargs={"parent_lookup_website": website.name},
            )
        )
        received_results = sorted(
            resp.data.get("results"), key=lambda user: (user["name"], user["user_id"])
        )
        assert received_results == expected_results


def test_websites_collaborators_endpoint_list_permission_denied(
    drf_client, permission_groups
):
    """Website editors should not be able to see the collaborators list"""
    drf_client.force_login(permission_groups.site_editor)
    resp = drf_client.get(
        reverse(
            "websites_collaborators_api-list",
            kwargs={"parent_lookup_website": permission_groups.websites[0].name},
        )
    )
    assert resp.status_code == 403


def test_websites_collaborators_endpoint_list_create(drf_client, permission_groups):
    """An admin should be able to add a new collaborator"""
    website = permission_groups.websites[0]
    collaborator = UserFactory.create()
    drf_client.force_login(permission_groups.site_admin)
    resp = drf_client.post(
        reverse(
            "websites_collaborators_api-list",
            kwargs={"parent_lookup_website": website.name},
        ),
        data={"email": collaborator.email, "role": constants.ROLE_EDITOR},
    )
    assert resp.status_code == 201
    resp_json = resp.json()
    assert resp_json == {
        "user_id": collaborator.id,
        "name": collaborator.name,
        "email": collaborator.email,
        "role": constants.ROLE_EDITOR,
    }
    assert website.editor_group.user_set.filter(id=collaborator.id) is not None


def test_websites_collaborators_endpoint_list_create_only_once(
    drf_client, permission_groups
):
    """An admin should not be able to add a new collaborator if already present"""
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.site_admin)
    resp = drf_client.post(
        reverse(
            "websites_collaborators_api-list",
            kwargs={"parent_lookup_website": website.name},
        ),
        data={
            "email": permission_groups.site_editor.email,
            "role": constants.ROLE_ADMINISTRATOR,
        },
    )
    assert resp.status_code == 400
    assert resp.json() == {"email": ["User is already a collaborator for this site"]}


@pytest.mark.parametrize(
    "role", [constants.GLOBAL_ADMIN, constants.GLOBAL_AUTHOR, "fake"]
)
def test_websites_collaborators_endpoint_list_create_bad_group(
    drf_client, permission_groups, role
):
    """An admin should not be able to add a new collaborator to a global/nonexistent group"""
    collaborator = UserFactory.create()
    drf_client.force_login(permission_groups.site_admin)
    resp = drf_client.post(
        reverse(
            "websites_collaborators_api-list",
            kwargs={"parent_lookup_website": permission_groups.websites[0].name},
        ),
        data={"email": collaborator.email, "role": role},
    )
    assert resp.status_code == 400
    assert resp.json() == {"role": ["Invalid role"]}


def test_websites_collaborators_endpoint_list_create_bad_user(
    drf_client, permission_groups
):
    """An admin should not be able to add a global admin, website owner, or nonexistent user to a group"""
    drf_client.force_login(permission_groups.site_admin)
    website = permission_groups.websites[0]
    for [email, error] in [
        [permission_groups.global_admin.email, {"email": ["User is a global admin"]}],
        [
            website.owner.email,
            {"email": ["User is already a collaborator for this site"]},
        ],
        ["fakeuser@test.edu", {"email": ["User does not exist"]}],
    ]:
        resp = drf_client.post(
            reverse(
                "websites_collaborators_api-list",
                kwargs={"parent_lookup_website": website.name},
            ),
            data={
                "email": email,
                "role": constants.ROLE_EDITOR,
            },
        )
        assert resp.status_code == 400
        assert resp.json() == error


@pytest.mark.parametrize(
    ("missing", "error"),
    [
        ["role", "Role is required"],  # noqa: PT007
        ["email", "Email is required"],  # noqa: PT007
    ],
)
def test_websites_collaborators_endpoint_detail_create_missing_data(
    drf_client, permission_groups, missing, error
):
    """A validation error should be raised if role or email is missing"""
    website = permission_groups.websites[0]
    data = {
        "email": UserFactory.create().email,
        "role": constants.ROLE_EDITOR,
    }
    data.pop(missing)

    drf_client.force_login(permission_groups.site_admin)
    resp = drf_client.post(
        reverse(
            "websites_collaborators_api-list",
            kwargs={"parent_lookup_website": website.name},
        ),
        data=data,
    )
    assert resp.status_code == 400
    assert resp.data == {missing: [error]}


def test_websites_collaborators_endpoint_detail(drf_client, permission_groups):
    """An admin should be able to view a collaborator detail"""
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.global_admin)
    for [user, role] in [
        [
            permission_groups.site_admin,
            constants.ROLE_ADMINISTRATOR,
        ],
        [
            permission_groups.global_admin,
            constants.GLOBAL_ADMIN,
        ],
        [website.owner, constants.ROLE_OWNER],
    ]:
        resp = drf_client.get(
            reverse(
                "websites_collaborators_api-detail",
                kwargs={
                    "parent_lookup_website": website.name,
                    "user_id": user.id,
                },
            )
        )
        assert resp.status_code == 200
        assert resp.data == {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "role": role,
        }


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_websites_collaborators_endpoint_detail_denied(
    drf_client, permission_groups, method
):
    """An editor should not be able to view/edit/delete a collaborator detail"""
    drf_client.force_login(permission_groups.site_editor)
    request_func = getattr(drf_client, method)
    resp = request_func(
        reverse(
            "websites_collaborators_api-detail",
            kwargs={
                "parent_lookup_website": permission_groups.websites[0].name,
                "user_id": permission_groups.site_admin.id,
            },
        )
    )
    assert resp.status_code == 403


def test_websites_collaborators_endpoint_detail_modify(drf_client, permission_groups):
    """An admin should be able to switch a collaborator from editor to admin"""
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.site_admin)
    resp = drf_client.patch(
        reverse(
            "websites_collaborators_api-detail",
            kwargs={
                "parent_lookup_website": website.name,
                "user_id": permission_groups.site_editor.id,
            },
        ),
        data={
            "role": constants.ROLE_ADMINISTRATOR,
        },
    )
    assert resp.status_code == 200
    assert website.admin_group.user_set.filter(
        id=permission_groups.site_admin.id
    ).exists()
    assert not website.editor_group.user_set.filter(
        id=permission_groups.site_admin.id
    ).exists()


def test_websites_collaborators_endpoint_detail_modify_admin_denied(
    drf_client, permission_groups
):
    """An admin should not be able to modify a global admin or website owner"""
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.site_admin)
    for user in [permission_groups.global_admin, website.owner]:
        resp = drf_client.patch(
            reverse(
                "websites_collaborators_api-detail",
                kwargs={
                    "parent_lookup_website": website.name,
                    "user_id": user.id,
                },
            ),
            data={
                "role": constants.ROLE_ADMINISTRATOR,
            },
        )
        assert resp.status_code == 403


def test_websites_collaborators_endpoint_detail_modify_missing_data(
    drf_client, permission_groups
):
    """A validation error should be raised if role is missing from a patch request"""
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.site_admin)

    resp = drf_client.patch(
        reverse(
            "websites_collaborators_api-detail",
            kwargs={
                "parent_lookup_website": website.name,
                "user_id": permission_groups.site_editor.id,
            },
        ),
        data={},
    )
    assert resp.status_code == 400
    assert resp.data == {"role": ["Role is required"]}


def test_websites_collaborators_endpoint_detail_modify_nonadmin_denied(
    drf_client, permission_groups
):
    """An editor or unaffiliated user should not be able to modify any collaborator"""
    website = permission_groups.websites[0]
    for client_user in (permission_groups.site_editor, UserFactory.create()):
        drf_client.force_login(client_user)
        resp = drf_client.patch(
            reverse(
                "websites_collaborators_api-detail",
                kwargs={
                    "parent_lookup_website": website.name,
                    "user_id": permission_groups.site_admin.id,
                },
            ),
            data={
                "role": constants.ROLE_EDITOR,
            },
        )
        assert resp.status_code == 403


def test_websites_collaborators_endpoint_detail_delete(drf_client, permission_groups):
    """An admin should be able to remove a collaborator"""
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.site_admin)
    resp = drf_client.delete(
        reverse(
            "websites_collaborators_api-detail",
            kwargs={
                "parent_lookup_website": website.name,
                "user_id": permission_groups.site_admin.id,
            },
        )
    )
    assert resp.status_code == 204
    assert not website.editor_group.user_set.filter(
        id=permission_groups.site_admin.id
    ).exists()
    assert not website.admin_group.user_set.filter(
        id=permission_groups.site_admin.id
    ).exists()

    # verify user was not deleted!
    assert User.objects.filter(id=permission_groups.site_admin.id).exists()


def test_websites_collaborators_endpoint_detail_delete_denied(
    drf_client, permission_groups
):
    """An admin should not be able to remove a global admin or owner"""
    website = permission_groups.websites[0]
    for user in (permission_groups.global_admin, website.owner):
        drf_client.force_login(permission_groups.site_admin)
        resp = drf_client.delete(
            reverse(
                "websites_collaborators_api-detail",
                kwargs={
                    "parent_lookup_website": website.name,
                    "user_id": user.id,
                },
            ),
            data={},
        )
        assert resp.status_code == 403
