"""General utility function tests"""
import pytest

from main.utils import (
    get_dirpath_and_filename,
    get_file_extension,
    remove_trailing_slashes,
)


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
