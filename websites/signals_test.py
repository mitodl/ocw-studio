"""Tests for signals"""

import pytest

from users.factories import UserFactory
from websites import constants
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.serializers import WebsiteContentDetailSerializer


@pytest.mark.django_db
def test_handle_website_save():
    """Groups should be created for a new Website"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    assert website.admin_group is not None
    assert website.editor_group is not None
    assert website.owner.has_perm(constants.PERMISSION_EDIT, website)


@pytest.mark.django_db
def test_navmenu_updated_on_page_title_change(mocker, enable_websitecontent_signal):
    """Navmenu pageRef and name are updated when a page's title changes"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    mocker.patch("websites.signals.is_feature_enabled", return_value=True)

    page = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_PAGE,
        dirpath="",
        title="Original Title",
        filename="original-title",
        text_id="abc123",
    )
    navmenu = WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_NAVMENU,
        metadata={
            constants.WEBSITE_CONTENT_LEFTNAV: [
                {
                    "identifier": "abc123",
                    "pageRef": "/pages/original-title",
                    "name": "Original Title",
                }
            ]
        },
    )

    page.title = "New Title"
    serializer = WebsiteContentDetailSerializer(
        instance=page, data={"title": "New Title"}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    navmenu.refresh_from_db()
    menu_item = navmenu.metadata[constants.WEBSITE_CONTENT_LEFTNAV][0]
    assert menu_item["pageRef"] == "/pages/new-title"
    assert menu_item["name"] == "New Title"
