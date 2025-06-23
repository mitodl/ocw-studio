"""Tests for signals"""

import pytest
from django.utils.text import slugify

from users.factories import UserFactory
from websites import constants
from websites.factories import WebsiteContentFactory, WebsiteFactory


@pytest.mark.django_db()
def test_handle_website_save():
    """Groups should be created for a new Website"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    assert website.admin_group is not None
    assert website.editor_group is not None
    assert website.owner.has_perm(constants.PERMISSION_EDIT, website)


@pytest.mark.django_db()
def test_update_page_url_on_title_change(mocker):
    """
    Filename should update to slugified title if feature flag
    is enabled and no conflict exists
    """
    website = WebsiteFactory.create(owner=UserFactory.create())
    mocker.patch("websites.signals.is_feature_enabled", return_value=True)

    page = WebsiteContentFactory.create(
        website=website, is_page_content=True, title="Test Page", filename="test-page"
    )
    page.title = "Some New Title"
    page.save()
    page.refresh_from_db()
    assert page.filename == slugify("Some New Title")
