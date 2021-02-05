""" Tests for signals """
import pytest

from websites.factories import WebsiteFactory


@pytest.mark.django_db
def test_handle_website_save():
    """ Groups should be created for a new Website """
    website = WebsiteFactory.create()
    assert website.admin_group is not None
    assert website.editor_group is not None
