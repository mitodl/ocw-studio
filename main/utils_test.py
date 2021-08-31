"""General utility function tests"""
import pytest

from main.utils import (
    are_equivalent_paths,
    get_dirpath_and_filename,
    get_file_extension,
    is_valid_uuid,
    remove_trailing_slashes,
    valid_key,
)


@pytest.mark.parametrize(
    "uuid_to_test, is_valid",
    [
        ["50fe3182-b1c9-ad10-de16-aeaae7f137cd", True],
        ["not-a-uuid", False],
        ["28bcec93-eb51-447e-84e1-ed453eea818e", True],
    ],
)
def test_is_valid_uuid(uuid_to_test, is_valid):
    """ is_valid_uuid should return True for a valid UUID, false otherwise """
    assert is_valid_uuid(uuid_to_test) is is_valid


@pytest.mark.parametrize(
    "filepath,exp_extension",
    [
        ["myfile.txt", "txt"],
        ["myfile.tar.gz", "tar.gz"],
        ["/path/to/myfile.docx", "docx"],
        ["myfile", ""],
        ["/path/to/myfile", ""],
    ],
)
def test_get_file_extension(filepath, exp_extension):
    """get_file_extension should return the file extension for a given filepath"""
    assert get_file_extension(filepath) == exp_extension


@pytest.mark.parametrize(
    "filepath,exp_result",
    [
        ["/my/path/", "my/path"],
        ["/my/path", "my/path"],
        ["my/path/", "my/path"],
        ["my/path", "my/path"],
        ["/my/path/myfile.pdf", "my/path/myfile.pdf"],
    ],
)
def test_remove_trailing_slashes(filepath, exp_result):
    """remove_trailing_slashes should remove slashes from the front and back of a file or directory path"""
    assert remove_trailing_slashes(filepath) == exp_result


@pytest.mark.parametrize(
    "filepath,expect_extension,exp_result",
    [
        ["/my/path/", True, ("my/path", None)],
        ["/my/path", True, ("my/path", None)],
        ["/my/path/myfile.pdf", True, ("my/path", "myfile")],
        ["/my/path/to/some.other-file.txt", True, ("my/path/to", "some.other-file")],
        ["/my/path/to/myfile", False, ("my/path/to", "myfile")],
    ],
)
def test_get_dirpath_and_filename(filepath, expect_extension, exp_result):
    """get_dirpath_and_filename should return a dirpath and filename from a filepath"""
    assert (
        get_dirpath_and_filename(filepath, expect_file_extension=expect_extension)
        == exp_result
    )


@pytest.mark.parametrize(
    "filepath1,filepath2,exp_result",
    [
        ["/my/path/", "/my/path/", True],
        ["/my/path/", "my/path", True],
        ["my/path/1", "my/path/2", False],
    ],
)
def test_are_equivalent_paths(filepath1, filepath2, exp_result):
    """are_equivalent_paths should return True if the given paths are equivalent"""
    assert are_equivalent_paths(filepath1, filepath2) is exp_result


@pytest.mark.parametrize(
    "key, is_valid", [["unit-test-me", True], ["wrong-key", False]]
)
def test_valid_key(mocker, key, is_valid):
    """ valid_key should return True for a valid key, false otherwise """
    mock_request = mocker.Mock(
        body=b'{"foo":"bar"}',
        headers={"X-Hub-Signature": "sha1=6a4e7673fa9c3afbb2860ae03ac2082958313a9c"},
    )
    assert valid_key(key, mock_request) is is_valid
