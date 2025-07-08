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
@pytest.mark.parametrize(
    (
        "is_page_content",
        "feature_flag",
        "initial_title",
        "new_title",
        "existing_conflict",
        "expected_filename",
    ),
    [
        # feature flag disabled; no URL change
        (True, False, "Original Title", "New Title", False, "original-title"),
        # conflict with existing slugified title; no URL change
        (True, True, "Original Title", "Some Existing Title", True, "original-title"),
        # non-page content; no URL change
        (False, True, "Original Title", "New Title", False, "original-title"),
        # slugified title matches existing filename; no URL change
        (True, True, "Test Page", "test page", False, "test-page"),
        # URL should be updated
        (True, True, "Test Page", "Some New Title", False, "some-new-title"),
    ],
)
def test_update_page_url_on_title_change_parametrized(  # noqa: PLR0913
    mocker,
    is_page_content,
    feature_flag,
    initial_title,
    new_title,
    existing_conflict,
    expected_filename,
):
    """Page filename is updated correctly when page's title changes"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    mocker.patch("websites.signals.is_feature_enabled", return_value=feature_flag)

    if existing_conflict:
        WebsiteContentFactory.create(
            website=website,
            is_page_content=True,
            dirpath="",
            title=new_title,
            filename=slugify(new_title),
        )

    page = WebsiteContentFactory.create(
        website=website,
        is_page_content=is_page_content,
        dirpath="",
        title=initial_title,
        filename=slugify(initial_title),
    )
    page.title = new_title
    page.save()
    page.refresh_from_db()
    assert page.filename == expected_filename


@pytest.mark.django_db()
def test_navmenu_updated_on_page_title_change(mocker):
    """Navmenu pageRef and name are updated when a page's title changes"""
    website = WebsiteFactory.create(owner=UserFactory.create())
    mocker.patch("websites.signals.is_feature_enabled", return_value=True)

    page = WebsiteContentFactory.create(
        website=website,
        is_page_content=True,
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
    page.save()
    navmenu.refresh_from_db()
    menu_item = navmenu.metadata[constants.WEBSITE_CONTENT_LEFTNAV][0]
    assert menu_item["pageRef"] == "/pages/new-title"
    assert menu_item["name"] == "New Title"
