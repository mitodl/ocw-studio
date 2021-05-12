""" Website models tests """
import pytest

from websites.factories import WebsiteContentFactory
from websites.models import WebsiteContent


def test_websitecontent_calculate_checksum():
    """ Verify calculate_checksum() returns a sha256 checksum """
    content = WebsiteContentFactory.build(
        markdown="content", metadata={"data": "value"}, content_filepath="_index.md"
    )

    # manually computed checksum in a python shell
    assert (
        content.calculate_checksum()
        == "cfcbebb93fdf56848f32afc3d1bda55868a465547de0e6fb4b8dab05b69ec352"
    )


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
