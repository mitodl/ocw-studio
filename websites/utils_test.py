"""Website utils tests"""
import pytest

from websites import constants
from websites.factories import WebsiteFactory
from websites.utils import permissions_group_name_for_role


@pytest.mark.parametrize(
    "role, group_prefix",
    [
        [constants.ROLE_ADMINISTRATOR, constants.ADMIN_GROUP_PREFIX],
        [constants.ROLE_EDITOR, constants.EDITOR_GROUP_PREFIX],
    ],
)
def test_permissions_group_name_for_role(role, group_prefix):
    """permissions_group_for_role should return the correct group name for a website and role"""
    website = WebsiteFactory.build()
    assert (
        permissions_group_name_for_role(role, website)
        == f"{group_prefix}{website.uuid.hex}"
    )


def test_permissions_group_name_for_global_admin():
    """permissions_group_for_role should return the correct group name for global admins"""
    website = WebsiteFactory.build()
    assert (
        permissions_group_name_for_role(constants.ROLE_GLOBAL, website)
        == constants.GLOBAL_ADMIN
    )


@pytest.mark.parametrize(
    "role",
    [constants.GLOBAL_AUTHOR, constants.ROLE_OWNER, "fake"],
)
def test_permissions_group_for_role_invalid(role):
    """permissions_group_for_role should raise a ValueError for an invalid role"""
    website = WebsiteFactory.build()
    with pytest.raises(ValueError) as exc:
        permissions_group_name_for_role(role, website)
    assert exc.value.args == (f"Invalid role for a website group: {role}",)
