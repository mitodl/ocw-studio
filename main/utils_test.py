"""General utility function tests"""

import pytest

from main.utils import (
    are_equivalent_paths,
    get_base_filename,
    get_dirpath_and_filename,
    get_file_extension,
    is_valid_uuid,
    remove_trailing_slashes,
    truncate_words,
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
