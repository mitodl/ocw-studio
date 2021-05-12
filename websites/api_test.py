"""Tests for websites API functionality"""
import factory
import pytest

from websites.api import get_valid_new_filename
from websites.factories import WebsiteContentFactory, WebsiteFactory


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("dirpath", ["path/to", None])
@pytest.mark.parametrize(
    "existing_filenames,exp_result_filename",
    [
        [[], "my-title"],
        [["my-title"], "my-title-2"],
        [["my-title", "my-title-9"], "my-title-10"],
    ],
)
def test_websitecontent_autogen_filename_unique(
    dirpath, existing_filenames, exp_result_filename
):
    """
    New WebsiteContent objects should have a unique filename generated if the initial auto-generated filename conflicts
    with an existing one.
    """
    filename_base = "my-title"
    content_type = "page"
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
            content_type=content_type,
            dirpath=dirpath,
            filename_base=filename_base,
        )
        == exp_result_filename
    )
