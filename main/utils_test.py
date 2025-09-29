"""General utility function tests"""

import pytest

from main.utils import (
    FeatureFlag,
    NestableKeyTextTransform,
    are_equivalent_paths,
    get_base_filename,
    get_dict_list_item_by_field,
    get_dirpath_and_filename,
    get_file_extension,
    is_dev,
    is_valid_uuid,
    remove_trailing_slashes,
    truncate_words,
    uuid_string,
    valid_key,
)


@pytest.mark.parametrize(
    ("uuid_to_test", "is_valid"),
    [
        ["50fe3182-b1c9-ad10-de16-aeaae7f137cd", True],  # noqa: PT007
        ["not-a-uuid", False],  # noqa: PT007
        ["28bcec93-eb51-447e-84e1-ed453eea818e", True],  # noqa: PT007
    ],
)
def test_is_valid_uuid(uuid_to_test, is_valid):
    """is_valid_uuid should return True for a valid UUID, false otherwise"""
    assert is_valid_uuid(uuid_to_test) is is_valid


@pytest.mark.parametrize(
    ("filepath", "exp_extension"),
    [
        ["myfile.txt", "txt"],  # noqa: PT007
        ["myfile.tar.gz", "tar.gz"],  # noqa: PT007
        ["/path/to/myfile.docx", "docx"],  # noqa: PT007
        ["myfile", ""],  # noqa: PT007
        ["/path/to/myfile", ""],  # noqa: PT007
    ],
)
def test_get_file_extension(filepath, exp_extension):
    """get_file_extension should return the file extension for a given filepath"""
    assert get_file_extension(filepath) == exp_extension


@pytest.mark.parametrize(
    ("filepath", "exp_result"),
    [
        ["/my/path/", "my/path"],  # noqa: PT007
        ["/my/path", "my/path"],  # noqa: PT007
        ["my/path/", "my/path"],  # noqa: PT007
        ["my/path", "my/path"],  # noqa: PT007
        ["/my/path/myfile.pdf", "my/path/myfile.pdf"],  # noqa: PT007
    ],
)
def test_remove_trailing_slashes(filepath, exp_result):
    """remove_trailing_slashes should remove slashes from the front and back of a file or directory path"""
    assert remove_trailing_slashes(filepath) == exp_result


@pytest.mark.parametrize(
    ("filepath", "expect_extension", "exp_result"),
    [
        ["/my/path/", True, ("my/path", None)],  # noqa: PT007
        ["/my/path", True, ("my/path", None)],  # noqa: PT007
        ["/my/path/myfile.pdf", True, ("my/path", "myfile")],  # noqa: PT007
        [  # noqa: PT007
            "/my/path/to/some.other-file.txt",
            True,
            ("my/path/to", "some.other-file"),
        ],
        ["/my/path/to/myfile", False, ("my/path/to", "myfile")],  # noqa: PT007
    ],
)
def test_get_dirpath_and_filename(filepath, expect_extension, exp_result):
    """get_dirpath_and_filename should return a dirpath and filename from a filepath"""
    assert (
        get_dirpath_and_filename(filepath, expect_file_extension=expect_extension)
        == exp_result
    )


@pytest.mark.parametrize(
    ("filepath1", "filepath2", "exp_result"),
    [
        ["/my/path/", "/my/path/", True],  # noqa: PT007
        ["/my/path/", "my/path", True],  # noqa: PT007
        ["my/path/1", "my/path/2", False],  # noqa: PT007
    ],
)
def test_are_equivalent_paths(filepath1, filepath2, exp_result):
    """are_equivalent_paths should return True if the given paths are equivalent"""
    assert are_equivalent_paths(filepath1, filepath2) is exp_result


@pytest.mark.parametrize(
    ("key", "is_valid"),
    [["unit-test-me", True], ["wrong-key", False]],  # noqa: PT007
)
def test_valid_key(mocker, key, is_valid):
    """valid_key should return True for a valid key, false otherwise"""
    mock_request = mocker.Mock(
        body=b'{"foo":"bar"}',
        headers={"X-Hub-Signature": "sha1=6a4e7673fa9c3afbb2860ae03ac2082958313a9c"},
    )
    assert valid_key(key, mock_request) is is_valid


@pytest.mark.parametrize(
    ("text", "truncated"),
    [["Hello world", "Hello___"], ["HelloWorld", "HelloW___"]],  # noqa: PT007
)
def test_truncate_words(text, truncated):
    """truncate_words returns expected result"""
    assert truncate_words(text, 9, suffix="___") == truncated


@pytest.mark.parametrize(
    ("filename", "expected_base_filename"),
    [
        ("file", "file"),
        ("file_ext", "file"),
        ("file_name_ext", "file_name"),
    ],
)
def test_get_base_filename(filename, expected_base_filename):
    """Test get_base_filename truncates extension"""
    assert get_base_filename(filename) == expected_base_filename


def test_uuid_string():
    """Test uuid_string generates valid UUID strings"""
    uuid_str = uuid_string()
    assert isinstance(uuid_str, str)
    assert is_valid_uuid(uuid_str)
    
    # Test that multiple calls generate different UUIDs
    uuid_str2 = uuid_string()
    assert uuid_str != uuid_str2


def test_feature_flag_enum():
    """Test FeatureFlag enum"""
    # Test that EXAMPLE_FEATURE has a power of 2 value
    assert FeatureFlag.EXAMPLE_FEATURE.value > 0
    # Test that it's a power of 2 (has only one bit set)
    assert (FeatureFlag.EXAMPLE_FEATURE.value & (FeatureFlag.EXAMPLE_FEATURE.value - 1)) == 0


def test_nestable_key_text_transform():
    """Test NestableKeyTextTransform class"""
    # Test with single path
    transform = NestableKeyTextTransform("field", "key1")
    assert transform is not None
    
    # Test with multiple paths
    transform = NestableKeyTextTransform("field", "key1", "key2", "key3")
    assert transform is not None
    
    # Test that empty path raises ValueError
    with pytest.raises(ValueError, match=r"Path must contain at least one key\."):
        NestableKeyTextTransform("field")


def test_is_dev(settings):
    """Test is_dev function"""
    # Test when ENVIRONMENT is "dev"
    settings.ENVIRONMENT = "dev"
    assert is_dev() is True
    
    # Test when ENVIRONMENT is not "dev"
    settings.ENVIRONMENT = "production"
    assert is_dev() is False
    
    settings.ENVIRONMENT = "staging"
    assert is_dev() is False


@pytest.mark.parametrize(
    ("items", "field", "value", "expected"),
    [
        # Test finding item in list
        ([{"name": "item1", "id": 1}, {"name": "item2", "id": 2}], "name", "item2", {"name": "item2", "id": 2}),
        # Test item not found
        ([{"name": "item1", "id": 1}, {"name": "item2", "id": 2}], "name", "item3", None),
        # Test empty list
        ([], "name", "item1", None),
        # Test field doesn't exist
        ([{"name": "item1", "id": 1}], "missing_field", "value", None),
        # Test with numeric values
        ([{"name": "item1", "id": 1}, {"name": "item2", "id": 2}], "id", 1, {"name": "item1", "id": 1}),
    ],
)
def test_get_dict_list_item_by_field(items, field, value, expected):
    """Test get_dict_list_item_by_field function"""
    result = get_dict_list_item_by_field(items, field, value)
    assert result == expected


def test_truncate_words_edge_cases():
    """Test truncate_words with edge cases"""
    # Test with content shorter than length
    assert truncate_words("short", 10) == "short"
    
    # Test with exact length
    assert truncate_words("exactly10c", 10) == "exactly10c"
    
    # Test with custom suffix
    assert truncate_words("This is a long sentence", 10, suffix=">>>") == "This is>>>>"
    
    # Test with None suffix
    assert truncate_words("This is a long sentence", 10, suffix=None) == "This isNone"
    
    # Test with empty suffix
    assert truncate_words("This is a long sentence", 10, suffix="") == "This is a "
    
    # Test with single word longer than length
    assert truncate_words("supercalifragilisticexpialidocious", 10) == "super..."
