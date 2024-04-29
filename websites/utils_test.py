"""Website utils tests"""

import pytest

from websites import constants
from websites.factories import WebsiteFactory
from websites.utils import (
    get_dict_query_field,
    permissions_group_name_for_role,
    set_dict_field,
)


@pytest.mark.parametrize(
    ("role", "group_prefix"),
    [
        [constants.ROLE_ADMINISTRATOR, constants.ADMIN_GROUP_PREFIX],  # noqa: PT007
        [constants.ROLE_EDITOR, constants.EDITOR_GROUP_PREFIX],  # noqa: PT007
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
    with pytest.raises(ValueError) as exc:  # noqa: PT011
        permissions_group_name_for_role(role, website)
    assert exc.value.args == (f"Invalid role for a website group: {role}",)


def test_get_dict_query_field():
    """Test get_dict_query_field"""
    assert (
        get_dict_query_field("metadata", "video_files.video_captions_file")
        == "metadata__video_files__video_captions_file"
    )


def test_set_dict_field():
    """The input dict should get updated with the expected keys/values"""
    input_dict = {"section_a": {"section_b": {"parameter_1": "a", "parameter_2": "b"}}}
    set_dict_field(input_dict, "section_a.section_b.parameter_3", "c")
    set_dict_field(input_dict, "section_a.new_param", "new_val_for_a")
    set_dict_field(input_dict, "section_a.section_b.parameter_2", "b_updated")
    set_dict_field(input_dict, "section_c.parameter_1", "new_section_val")
    set_dict_field(input_dict, "video_files.parameter_1", "value1")
    set_dict_field(input_dict, "video_files.parameter_2", "value2")
    assert input_dict == {
        "section_a": {
            "new_param": "new_val_for_a",
            "section_b": {
                "parameter_1": "a",
                "parameter_2": "b_updated",
                "parameter_3": "c",
            },
        },
        "section_c": {"parameter_1": "new_section_val"},
        "video_files": {
            "parameter_1": "value1",
            "parameter_2": "value2",
        },
    }
