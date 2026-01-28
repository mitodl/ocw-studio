"""Website utils tests"""

import pytest

from websites import constants
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.utils import (
    compile_referencing_content,
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
        # Test case 12: Unquoted UUID in resource_link (user's failing case)
        (
            'asdhgfhgf  {{% resource_link 5e104a4b-ffe0-67b3-5506-f301bef2d39f "PDF" %}}',
            ["5e104a4b-ffe0-67b3-5506-f301bef2d39f"],
        ),
        # Test case 13: Mixed quoted and unquoted UUIDs
        (
            '{{% resource_link abcd1234-5678-90ef-abcd-123456789012 "Unquoted" %}} and {{% resource_link "efab5678-90ab-cdef-1234-567890abcdef" "Quoted" %}}',
            [
                "abcd1234-5678-90ef-abcd-123456789012",
                "efab5678-90ab-cdef-1234-567890abcdef",
            ],
        ),
        # Test case 14: Extra whitespace variations with unquoted UUID
        (
            '{{%  resource_link   1234abcd-ef56-7890-abcd-123456789012   "Title"   %}}',
            ["1234abcd-ef56-7890-abcd-123456789012"],
        ),
        # Test case 15: Unquoted UUID with complex title
        (
            '{{% resource_link fedcba98-7654-3210-fedc-ba9876543210 "Complex Title with 123 Numbers & Symbols!" %}}',
            ["fedcba98-7654-3210-fedc-ba9876543210"],
        ),
        # Test case 16: Unquoted UUID in resource shortcode
        (
            "{{< resource uuid=abcdef01-2345-6789-abcd-ef0123456789 >}}",
            ["abcdef01-2345-6789-abcd-ef0123456789"],
        ),
        # Test case 17: Mixed quoted resource_link and unquoted resource shortcode
        (
            '{{% resource_link "11111111-2222-3333-4444-555555555555" "Link" %}} and {{< resource uuid=66666666-7777-8888-9999-000000000000 >}}',
            [
                "11111111-2222-3333-4444-555555555555",
                "66666666-7777-8888-9999-000000000000",
            ],
        ),
        # Test case 18: Unquoted resource shortcode with extra whitespace
        (
            "{{<  resource  uuid=fedcba98-7654-3210-fedc-ba9876543210  >}}",
            ["fedcba98-7654-3210-fedc-ba9876543210"],
        ),
        # Edge cases: Malformed patterns
        # Missing closing
        (
            '{{% resource_link "123e4567-e89b-12d3-a456-426614174000" "title"',
            [],
        ),
        # Missing closing
        (
            '{{< resource uuid="123e4567-e89b-12d3-a456-426614174000"',
            [],
        ),
        # Invalid UUID
        (
            '{{% resource_link "123e4567-e89b-12d3-a456-426614174000x" "title" %}}',
            [],
        ),
        # Invalid UUID
        (
            '{{< resource uuid="123e4567-e89b-12d3-a456-426614174000extra" >}}',
            [],
        ),
        # Missing title
        (
            '{{% resource_link "123e4567-e89b-12d3-a456-426614174000" %}}',
            [],
        ),
        # Wrong UUID format
        (
            '{{% resource_link "123e4567-e89b-12d3-a456-42661417400" "title" %}}',
            [],
        ),
        # Extra dash
        (
            '{{% resource_link "123e4567-e89b-12d3-a456-426614174000-extra" "title" %}}',
            [],
        ),
        # Edge cases: Extreme whitespace (valid patterns)
        (
            '   {{% resource_link    12345678-abcd-1234-5678-123456789012    "title"    %}}   ',
            ["12345678-abcd-1234-5678-123456789012"],
        ),
        (
            '{{<    resource    uuid="87654321-dcba-4321-8765-210987654321"    >}}',
            ["87654321-dcba-4321-8765-210987654321"],
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


def test_compile_referencing_content_navmenu_type():
    """Test compile_referencing_content with NAVMENU content type"""
    # Create content with NAVMENU type and leftnav metadata
    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_NAVMENU,
        metadata={
            constants.WEBSITE_CONTENT_LEFTNAV: [
                {"identifier": "12345678-90ab-cdef-1234-567890abcdef"},
                {"identifier": "abcdef12-3456-789a-bcde-f1234567890a"},
                {"identifier": "99887766-5544-3322-1100-ffeeddccbbaa"},
            ]
        },
        markdown="This markdown should be ignored for navmenu type",
    )

    result = compile_referencing_content(content)
    expected = [
        "12345678-90ab-cdef-1234-567890abcdef",
        "abcdef12-3456-789a-bcde-f1234567890a",
        "99887766-5544-3322-1100-ffeeddccbbaa",
    ]
    assert result == expected


def test_compile_referencing_content_navmenu_empty():
    """Test compile_referencing_content with NAVMENU type but empty/no leftnav"""
    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_NAVMENU,
        metadata={constants.WEBSITE_CONTENT_LEFTNAV: []},
        markdown="This markdown should be ignored",
    )

    result = compile_referencing_content(content)
    assert result == []


def test_compile_referencing_content_page_markdown():
    """Test compile_referencing_content with PAGE type containing markdown references"""
    markdown_content = (
        '{{% resource_link "550e8400-e29b-41d4-a716-446655440001" "Resource 1" %}} '
        'and {{< resource uuid="550e8400-e29b-41d4-a716-446655440002" >}}'
    )

    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_PAGE,
        markdown=markdown_content,
        metadata={},
    )

    result = compile_referencing_content(content)
    expected = [
        "550e8400-e29b-41d4-a716-446655440001",
        "550e8400-e29b-41d4-a716-446655440002",
    ]
    assert result == expected


def test_compile_referencing_content_description_metadata():
    """Test compile_referencing_content with RESOURCE_LIST and RESOURCE_COLLECTION types having description metadata"""
    # Test RESOURCE_LIST type
    content_list = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE_LIST,
        markdown='{{% resource_link "11223344-5566-7788-99aa-bbccddee1122" "Markdown Resource" %}}',
        metadata={
            "description": '{{< resource uuid="66778899-aabb-ccdd-eeff-112233445566" >}}',
            "other_field": "This should be ignored",
        },
    )

    result_list = compile_referencing_content(content_list)
    expected = [
        "11223344-5566-7788-99aa-bbccddee1122",
        "66778899-aabb-ccdd-eeff-112233445566",
    ]
    assert result_list == expected

    # Test RESOURCE_COLLECTION type with same metadata structure
    content_collection = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE_COLLECTION,
        markdown='{{% resource_link "11223344-5566-7788-99aa-bbccddee1122" "Markdown Resource" %}}',
        metadata={
            "description": '{{< resource uuid="66778899-aabb-ccdd-eeff-112233445566" >}}',
            "other_field": "This should be ignored",
        },
    )

    result_collection = compile_referencing_content(content_collection)
    assert result_collection == expected


def test_compile_referencing_content_metadata_course_description():
    """Test compile_referencing_content with METADATA type having course_description"""
    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_METADATA,
        markdown='Some markdown with {{< resource uuid="aaaabbbb-cccc-dddd-eeee-ffff12345678" >}}',
        metadata={
            "course_description": '{{% resource_link "ffffeedd-ccbb-aa99-8877-665544332211" "Course Description" %}}',
            "other_metadata": "Should be ignored",
        },
    )

    result = compile_referencing_content(content)
    expected = [
        "aaaabbbb-cccc-dddd-eeee-ffff12345678",
        "ffffeedd-ccbb-aa99-8877-665544332211",
    ]
    assert result == expected


def test_compile_referencing_content_resource_image_metadata():
    """Test compile_referencing_content with RESOURCE type having image_metadata caption and credit"""
    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE,
        markdown='Resource markdown with {{< resource uuid="11223344-5566-7788-99aa-bbccddee1122" >}}',
        metadata={
            "image_metadata": {
                "caption": 'Caption with {{% resource_link "aaaabbbb-cccc-dddd-eeee-ffff12345678" "Caption Link" %}}',
                "credit": 'Credit with {{< resource uuid="ffffeedd-ccbb-aa99-8877-665544332211" >}}',
            },
            "other_field": "Should be ignored",
        },
    )

    result = compile_referencing_content(content)
    expected = [
        "11223344-5566-7788-99aa-bbccddee1122",  # From markdown
        "aaaabbbb-cccc-dddd-eeee-ffff12345678",  # From image_metadata.caption
        "ffffeedd-ccbb-aa99-8877-665544332211",  # From image_metadata.credit
    ]
    assert result == expected


def test_compile_referencing_content_resource_partial_image_metadata():
    """Test compile_referencing_content with RESOURCE type having only caption or credit"""
    # Test with only caption
    content_caption_only = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE,
        markdown=None,
        metadata={
            "image_metadata": {
                "caption": '{{< resource uuid="aaaabbbb-cccc-dddd-eeee-ffff12345678" >}}',
                # No credit field
            },
        },
    )

    result_caption = compile_referencing_content(content_caption_only)
    assert result_caption == ["aaaabbbb-cccc-dddd-eeee-ffff12345678"]

    # Test with only credit
    content_credit_only = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE,
        markdown=None,
        metadata={
            "image_metadata": {
                # No caption field
                "credit": '{{% resource_link "ffffeedd-ccbb-aa99-8877-665544332211" "Credit Link" %}}',
            },
        },
    )

    result_credit = compile_referencing_content(content_credit_only)
    assert result_credit == ["ffffeedd-ccbb-aa99-8877-665544332211"]


def test_compile_referencing_content_resource_no_image_metadata():
    """Test compile_referencing_content with RESOURCE type having no image_metadata"""
    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE,
        markdown='Only markdown {{< resource uuid="11223344-5566-7788-99aa-bbccddee1122" >}}',
        metadata={
            "title": "Some resource title",
            "other_field": "Some other data",
        },
    )

    result = compile_referencing_content(content)
    assert result == ["11223344-5566-7788-99aa-bbccddee1122"]


def test_compile_referencing_content_empty_and_none():
    """Test compile_referencing_content with no/empty markdown and metadata"""
    # Test with None values
    content_none = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_PAGE,
        markdown=None,
        metadata=None,
    )
    assert compile_referencing_content(content_none) == []

    # Test with empty values
    content_empty = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_PAGE,
        markdown="",
        metadata={},
    )
    assert compile_referencing_content(content_empty) == []

    # Test with markdown containing no resource references
    content_plain = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_PAGE,
        markdown="This is just plain text with no resource links or shortcodes.",
        metadata={},
    )
    assert compile_referencing_content(content_plain) == []


def test_compile_referencing_content_unexpected_metadata_type(caplog):
    """Test compile_referencing_content logs warning for unexpected metadata types"""
    content = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_METADATA,
        markdown=None,
        metadata={
            "course_description": 12345,
        },
    )

    result = compile_referencing_content(content)

    assert result == []
    assert "Unexpected metadata type" in caplog.text
    assert "int" in caplog.text
    assert "course_description" in caplog.text


def test_get_metadata_content_key():
    """Test get_metadata_content_key returns correct keys based on content type."""

    # Test RESOURCE_LIST type
    content_resource_list = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE_LIST
    )
    assert get_metadata_content_key(content_resource_list) == [
        constants.METADATA_FIELD_DESCRIPTION
    ]

    # Test RESOURCE_COLLECTION type
    content_resource_collection = WebsiteContentFactory.build(
        type=constants.CONTENT_TYPE_RESOURCE_COLLECTION
    )
    assert get_metadata_content_key(content_resource_collection) == [
        constants.METADATA_FIELD_DESCRIPTION
    ]

    # Test METADATA type
    content_metadata = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_METADATA)
    assert get_metadata_content_key(content_metadata) == [
        constants.METADATA_FIELD_COURSE_DESCRIPTION,
        constants.INSTRUCTORS_FIELD_CONTENT,
    ]

    # Test RESOURCE type (new case)
    content_resource = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_RESOURCE)
    assert get_metadata_content_key(content_resource) == [
        constants.METADATA_FIELD_IMAGE_CAPTION,
        constants.METADATA_FIELD_IMAGE_CREDIT,
    ]

    # Test unknown/unsupported type
    content_page = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_PAGE)
    assert get_metadata_content_key(content_page) == []

    # Test another unsupported type
    content_navmenu = WebsiteContentFactory.build(type=constants.CONTENT_TYPE_NAVMENU)
    assert get_metadata_content_key(content_navmenu) == []
