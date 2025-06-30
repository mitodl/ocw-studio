"""Website utils tests"""

import pytest

from websites import constants
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.utils import (
    get_dict_field,
    get_dict_query_field,
    get_metadata_content_key,
    parse_resource_uuid,
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


def test_get_dict_field():
    """Test get_dict_field for retrieving nested dictionary values"""
    test_dict = {
        "level1": {
            "level2": {"level3": "deep_value", "other_field": "other_value"},
            "direct_field": "direct_value",
        },
        "top_level": "top_value",
    }

    # Test nested field access
    assert get_dict_field(test_dict, "level1.level2.level3") == "deep_value"
    assert get_dict_field(test_dict, "level1.level2.other_field") == "other_value"
    assert get_dict_field(test_dict, "level1.direct_field") == "direct_value"
    assert get_dict_field(test_dict, "top_level") == "top_value"

    # Test non-existent paths
    assert get_dict_field(test_dict, "level1.level2.nonexistent") is None
    assert get_dict_field(test_dict, "level1.nonexistent.field") is None
    assert get_dict_field(test_dict, "nonexistent") is None

    # Test empty dict
    assert get_dict_field({}, "any.field") is None


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


@pytest.mark.parametrize(
    ("input_text", "expected_uuids"),
    [
        # Test case 1: Empty string
        ("", []),
        # Test case 2: String with no resource patterns
        ("This is just plain text with no resources", []),
        # Test case 3: Single resource_link pattern
        (
            '{{% resource_link "b02b216b-1e9e-4b5c-8b1b-9c275a834679" "Some Title" %}}',
            ["b02b216b-1e9e-4b5c-8b1b-9c275a834679"],
        ),
        # Test case 4: Single resource shortcode pattern
        (
            '{{< resource uuid="dbcd885b-f9a6-419d-8fd9-a7ddb67b94c5" >}}',
            ["dbcd885b-f9a6-419d-8fd9-a7ddb67b94c5"],
        ),
        # Test case 5: Multiple resource shortcode patterns (your original example)
        (
            '{{< resource uuid="b02b216b-1e9e-4b5c-8b1b-9c275a834679" >}}\n{{< resource uuid="dbcd885b-f9a6-419d-8fd9-a7ddb67b94c5" >}}',
            [
                "b02b216b-1e9e-4b5c-8b1b-9c275a834679",
                "dbcd885b-f9a6-419d-8fd9-a7ddb67b94c5",
            ],
        ),
        # Test case 6: Mixed patterns
        (
            '{{% resource_link "a1b2c3d4-e5f6-7890-abcd-ef1234567890" "Title 1" %}}\n{{< resource uuid="f9e8d7c6-b5a4-3210-9876-543210fedcba" >}}',
            [
                "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "f9e8d7c6-b5a4-3210-9876-543210fedcba",
            ],
        ),
        # Test case 7: Resource shortcode with extra whitespace
        (
            '{{< resource uuid="12345678-1234-1234-1234-123456789012"   >}}',
            ["12345678-1234-1234-1234-123456789012"],
        ),
        # Test case 8: Resource link with complex title
        (
            '{{% resource_link "87654321-4321-4321-4321-210987654321" "Complex Title with Numbers 123 and Symbols!" %}}',
            ["87654321-4321-4321-4321-210987654321"],
        ),
        # Test case 9: Multiple resource_link patterns
        (
            '{{% resource_link "11111111-2222-3333-4444-555555555555" "First" %}}\n{{% resource_link "66666666-7777-8888-9999-000000000000" "Second" %}}',
            [
                "11111111-2222-3333-4444-555555555555",
                "66666666-7777-8888-9999-000000000000",
            ],
        ),
        # Test case 10: Text with invalid UUID format (should not match)
        (
            '{{< resource uuid="invalid-uuid-format" >}}',
            [],
        ),
        # Test case 11: Partial matches that shouldn't work
        (
            "Some text with {{< resource uuid= and other incomplete patterns",
            [],
        ),
    ],
)
def test_parse_resource_uuid(input_text, expected_uuids):
    """Test parse_resource_uuid extracts UUIDs correctly from various resource patterns"""
    result = parse_resource_uuid(input_text)
    assert result == expected_uuids


def test_parse_resource_uuid_with_surrounding_text():
    """Test parse_resource_uuid works correctly when resource patterns are embedded in other text"""
    text = """
    This is some markdown content before the resource.

    {{< resource uuid="123e4567-e89b-12d3-a456-426614174000" >}}

    Here is some content in between resources.

    {{% resource_link "987fcdeb-ba01-2345-6789-abcdef012345" "My Resource Title" %}}

    And here is some content after the resources.
    """

    result = parse_resource_uuid(text)
    expected = [
        "123e4567-e89b-12d3-a456-426614174000",
        "987fcdeb-ba01-2345-6789-abcdef012345",
    ]
    assert result == expected


def test_parse_resource_uuid_case_sensitivity():
    """Test that parse_resource_uuid is case sensitive for the pattern matching"""
    # These should not match because of case differences
    invalid_cases = [
        '{{< Resource uuid="123e4567-e89b-12d3-a456-426614174000" >}}',  # Capital R
        '{{< RESOURCE UUID="123e4567-e89b-12d3-a456-426614174000" >}}',  # All caps
        '{{% RESOURCE_LINK "123e4567-e89b-12d3-a456-426614174000" "title" %}}',  # All caps
    ]

    for text in invalid_cases:
        result = parse_resource_uuid(text)
        assert result == [], f"Expected no matches for: {text}"


def test_get_metadata_content_key():
    """Test get_metadata_content_key returns correct keys based on content type."""

    # Test RESOURCE_LIST type
    content_resource_list = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE_LIST
    )
    assert get_metadata_content_key(content_resource_list) == ["description"]

    # Test RESOURCE_COLLECTION type
    content_resource_collection = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE_COLLECTION
    )
    assert get_metadata_content_key(content_resource_collection) == ["description"]

    # Test METADATA type
    content_metadata = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_METADATA)
    assert get_metadata_content_key(content_metadata) == ["course_description"]

    # Test RESOURCE type (new case)
    content_resource = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_RESOURCE)
    assert get_metadata_content_key(content_resource) == [
        "image_metadata.caption",
        "image_metadata.credit",
    ]

    # Test unknown/unsupported type
    content_page = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_PAGE)
    assert get_metadata_content_key(content_page) == []

    # Test another unsupported type
    content_navmenu = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_NAVMENU)
    assert get_metadata_content_key(content_navmenu) == []
