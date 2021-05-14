"""Tests for websites API functionality"""
import factory
import pytest

from websites.api import get_valid_new_filename
from websites.factories import WebsiteContentFactory, WebsiteFactory


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "existing_filenames,exp_result_filename",
    [
        [[], "my-title"],
        [["my-title"], "my-title2"],
        [["my-title", "my-title9"], "my-title10"],
        [["my-long-title", "my-long-title9"], "my-long-titl10"],
    ],
)
def test_websitecontent_autogen_filename_unique(
    mocker, existing_filenames, exp_result_filename
):
    """
    get_valid_new_filename should return a filename that obeys uniqueness constraints, adding a suffix and
    removing characters from the end of the string as necessary.
    """
    # Set a lower limit for max filename length to test that filenames are truncated appropriately
    mocker.patch("websites.api.CONTENT_FILENAME_MAX_LEN", 14)
    filename_base = (
        exp_result_filename if not existing_filenames else existing_filenames[0]
    )
    content_type = "page"
    dirpath = "path/to"
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        len(existing_filenames),
        website=website,
        type=content_type,
        dirpath=dirpath,
        filename=factory.Iterator(existing_filenames),
    )
    assert (
        get_valid_new_filename(
            website_pk=website.pk,
            dirpath=dirpath,
            filename_base=filename_base,
        )
        == exp_result_filename
    )
