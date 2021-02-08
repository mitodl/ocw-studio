""" Tests for signals """
import pytest

from users.factories import UserFactory
from websites import constants
from websites.factories import WebsiteFactory


@pytest.mark.django_db
def test_handle_website_save():
    """ Groups should be created for a new Website """
    website = WebsiteFactory.create(owner=UserFactory.create())
    assert website.admin_group is not None
    assert website.editor_group is not None
    assert website.owner.has_perm(constants.PERMISSION_EDIT, website)
