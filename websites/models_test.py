""" Website models tests """
import pytest

from websites.factories import WebsiteContentFactory
from websites.models import WebsiteContent


@pytest.mark.parametrize(
    "metadata, markdown, dirpath, exp_checksum",
    [
        [
            {"my": "metadata"},
            "# Markdown",
            None,
            "8ba489693daddd16de0e9f9b2a6a243ed764d79341cf353bbad0b2b399140ba4",
        ],
        [
            {"my": "metadata"},
            None,
            "path/to",
            "dad8e87334675a60de694397bd6ab592ed83ea3fda3fe7e74446c636479fed4d",
        ],
        [
            None,
            "# Markdown",
            "path/to",
            "9bba658e2a2bf057f8ce9132eb6454fe64430614f1431ea84e6ffc3a02613601",
        ],
    ],
)
def test_websitecontent_calculate_checksum(metadata, markdown, dirpath, exp_checksum):
    """ Verify calculate_checksum() returns the expected sha256 checksum """
    content = WebsiteContentFactory.build(
        markdown=markdown,
        metadata=metadata,
        dirpath=dirpath,
        filename="myfile",
        type="mytype",
        title="My Title",
    )
    # manually computed checksum in a python shell
    assert content.calculate_checksum() == exp_checksum


@pytest.mark.django_db
@pytest.mark.parametrize(
    "title, exp_generated_filename",
    [
        ["My Title", "my-title"],
        ["My... Title!", "my-title"],
        ["My Title My Title My Title", "my-title-my-ti"],
    ],
)
def test_websitecontent_generate_filename(mocker, title, exp_generated_filename):
    """
    WebsiteContent.generate_filename should generate a filename from a title with the correct length.
    """
    # Set a lower limit for max filename length to test that filenames are truncated appropriately
    mocker.patch("websites.models.CONTENT_FILENAME_MAX_LEN", 14)
    generated_filename = WebsiteContent.generate_filename(title=title)
    assert generated_filename == exp_generated_filename
