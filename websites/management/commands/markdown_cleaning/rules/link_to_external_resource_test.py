"""Tests for link_to_external_resource.py"""

from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from django.conf import settings

from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.rules.link_to_external_resource import (
    LinkToExternalResourceRule,
    NavItemToExternalResourceRule,
    build_external_resource,
    get_or_build_external_resource,
    is_ocw_domain_url,
)
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig

SAMPLE_SITE_CONFIG = {
    "collections": [
        {
            "category": "Content",
            "fields": [
                {
                    "help": "The URL. For example, https://owl.english.purdue.edu/owl/resource/747/01/\n",
                    "label": "URL",
                    "name": "external_url",
                    "required": True,
                    "widget": "string",
                },
                {
                    "default": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                    "label": "License",
                    "name": "license",
                    "options": [
                        {
                            "label": "CC BY-NC-SA",
                            "value": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                        },
                        {
                            "label": "CC BY",
                            "value": "https://creativecommons.org/licenses/by/4.0/",
                        },
                    ],
                    "required": True,
                    "widget": "select",
                },
                {
                    "default": True,
                    "help": "If true, user sees warning that external content is not covered by OCW licensing.\n",
                    "label": "Include non-OCW licensing warning",
                    "name": "has_external_license_warning",
                    "required": True,
                    "widget": "boolean",
                },
            ],
            "folder": "content/external-resources",
            "label": "External Resources",
            "name": "external-resource",
        },
    ],
    "root-url-path": "courses",
    "site-url-format": "[sitemetadata:primary_course_number]-[sitemetadata:course_title]-[sitemetadata:term]-[sitemetadata:year]",
}

pytestmark = pytest.mark.django_db


def get_cleaner(rule_type):
    """Get cleaner for this test module."""
    if rule_type == "markdown":
        rule = LinkToExternalResourceRule()
    else:
        rule = NavItemToExternalResourceRule()

    rule.set_options({"commit": True})

    return Cleaner(rule)


@pytest.mark.parametrize(
    ("url", "expected_result"),
    [
        ("https://ocw.mit.edu", True),
        ("https://google.com", False),
    ],
)
@patch("django.conf.settings.SITEMAP_DOMAIN", "ocw.mit.edu")
def test_is_ocw_domain_url(url, expected_result):
    """Test is_ocw_domain_url."""
    result = is_ocw_domain_url(url)
    assert result == expected_result


def test_build_external_resource():
    """Test build_external_resource."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    title = "title"
    url = "https://google.com"

    external_resource = build_external_resource(
        website=website,
        site_config=SiteConfig(SAMPLE_SITE_CONFIG),
        title=title,
        url=url,
    )

    assert external_resource.title == title
    assert external_resource.metadata["external_url"] == url
    assert external_resource.metadata["has_external_license_warning"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("content_exists", [True, False])
def test_get_or_build_external_resource(content_exists):
    """Test get_or_build_external_resource builds or gets depending on content existence."""
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        title = "title"
        url = "https://google.com"
        site_config = SiteConfig(SAMPLE_SITE_CONFIG)
        config_item = site_config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)

        if content_exists:
            existing_content = WebsiteContentFactory.create(
                metadata={
                    "external_url": url,
                    "has_external_license_warning": True,
                },
                dirpath=config_item.file_target,
                website=website,
                type=CONTENT_TYPE_EXTERNAL_RESOURCE,
                title=title,
            )

        external_resource = get_or_build_external_resource(
            website=website,
            site_config=SiteConfig(SAMPLE_SITE_CONFIG),
            title=title,
            url=url,
        )

    assert external_resource.title == title
    assert external_resource.metadata["external_url"] == url
    assert external_resource.metadata["has_external_license_warning"] is True

    if content_exists:
        assert existing_content.id == external_resource.id


@pytest.mark.parametrize(
    ("content", "expected_content_template"),
    [
        (
            R"""
            ![image](https://example.com/image.jpg)
            [invalid url](https://www.example website.com)
            [internal url](/pages/page)
            [OCW](https://ocw.mit.edu)
            [OCW clone](https://ocw.mit.edu)
            [OCW same but not so](https://ocw.mit.edu#fragment)
            """,
            R"""
            ![image](https://example.com/image.jpg)
            [invalid url](https://www.example website.com)
            [internal url](/pages/page)
            {{{{% resource_link "{text_id_1}" "OCW" %}}}}
            {{{{% resource_link "{text_id_1}" "OCW clone" %}}}}
            {{{{% resource_link "{text_id_2}" "OCW same but not so" %}}}}
            """,
        ),
    ],
)
def test_link_to_external_resources(settings, content, expected_content_template):
    """
    Test link_to_external_resources correctly replaces links
    with resource_link shortcode.
    """
    with patch(
        "external_resources.signals.submit_url_to_wayback_task.delay", return_value=None
    ):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        target_content = WebsiteContentFactory.create(
            markdown=content,
            website=website,
            metadata={
                "description": content,
                "related_resources_text": content,
                "optional_text": content,
                "course_description": content,
                "image_metadata": {
                    "caption": content,
                    "credit": content,
                },
            },
        )

        cleaner = get_cleaner("markdown")
        cleaner.update_website_content(target_content)

    wc_ocw = WebsiteContent.objects.get(title="OCW")
    wc_ocw_2 = WebsiteContent.objects.get(title="OCW same but not so")

    expected_content = expected_content_template.format(
        text_id_1=wc_ocw.text_id, text_id_2=wc_ocw_2.text_id
    )

    assert target_content.markdown == expected_content

    for field in [
        "description",
        "related_resources_text",
        "optional_text",
        "course_description",
    ]:
        assert target_content.metadata[field] == expected_content

    for field in ["credit", "caption"]:
        assert target_content.metadata["image_metadata"][field] == expected_content


@pytest.mark.parametrize(
    ("content", "expected_content_template"),
    [
        (
            [
                {
                    "name": "Nest",
                    "url": "https://ocw.mit.edu",
                    "weight": 10,
                    "identifier": "external--760432549-1711617249481",
                },
                {
                    "name": "Bird 1",
                    "url": "https://ocw.mit.edu",
                    "weight": 10,
                    "identifier": "external--760432549-1711617249482",
                    "parent": "external--760432549-1711617249481",
                },
                {
                    "name": "Bird 2",
                    "url": "https://ocw.mit.edu",
                    "weight": 20,
                    "identifier": "external--760432549-1711617249483",
                    "parent": "external--760432549-1711617249481",
                },
                {
                    "name": "Egg",
                    "url": "https://ocw.mit.edu",
                    "weight": 10,
                    "identifier": "external--760432549-1711617249484",
                    "parent": "external--760432549-1711617249483",
                },
                {
                    "name": "Control",
                    "weight": 20,
                    "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317",
                },
            ],
            [
                {"name": "Nest", "weight": 10, "identifier": "nest-id"},
                {
                    "name": "Bird 1",
                    "weight": 10,
                    "identifier": "bird-1-id",
                    "parent": "nest-id",
                },
                {
                    "name": "Bird 2",
                    "weight": 20,
                    "identifier": "bird-2-id",
                    "parent": "nest-id",
                },
                {
                    "name": "Egg",
                    "weight": 10,
                    "identifier": "egg-id",
                    "parent": "bird-2-id",
                },
                {
                    "name": "Control",
                    "weight": 20,
                    "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317",
                },
            ],
        ),
    ],
)
def test_nav_item_to_external_resources(content, expected_content_template):
    """Test nav_item_to_external_resource correctly converts external links to external resources."""
    with patch(
        "external_resources.signals.submit_url_to_wayback_task.delay", return_value=None
    ):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)

        target_content = WebsiteContentFactory.create(
            website=website,
            metadata={
                "leftnav": content,
            },
        )

        cleaner = get_cleaner("nav_item")
        cleaner.update_website_content(target_content)

    # Get all external resource content created by the rule
    external_resources = WebsiteContent.objects.filter(
        website=website, type=CONTENT_TYPE_EXTERNAL_RESOURCE
    ).order_by("title")

    # Since all nav items point to the same URL, they should all reference the same external resource
    # The rule creates only one external resource per unique URL
    assert external_resources.count() == 1
    shared_resource = external_resources.first()

    # All 4 nav items should now reference the same external resource
    expected_content = expected_content_template
    for item in expected_content:
        if item["name"] == "Control":
            continue
        # All external nav items should now use the same resource identifier
        item["identifier"] = shared_resource.text_id
        # Update parent references to also use the shared resource identifier
        if (
            item.get("parent")
            and item["parent"] != "f3d0ebae-7083-4524-9b93-f688537a0317"
        ):
            item["parent"] = shared_resource.text_id

    assert target_content.metadata["leftnav"] == expected_content


def test_rules_default_commit_value():
    """Test that both rules properly handle options when set."""
    link_rule = LinkToExternalResourceRule()
    nav_rule = NavItemToExternalResourceRule()

    # Set options using the inherited method
    link_rule.set_options({"commit": True})
    nav_rule.set_options({"commit": True})

    # Verify options are set correctly
    assert hasattr(link_rule, "options")
    assert link_rule.options is not None
    assert hasattr(nav_rule, "options")
    assert nav_rule.options is not None
    assert link_rule.options.get("commit", False) is True
    assert nav_rule.options.get("commit", False) is True

    # Test with False
    link_rule.set_options({"commit": False})
    nav_rule.set_options({"commit": False})

    assert link_rule.options.get("commit", True) is False
    assert nav_rule.options.get("commit", True) is False


def test_link_to_external_resource_no_save_when_commit_false(mocker):
    """Test that external resource is not saved when commit is False."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    mock_resource = mocker.Mock(spec=WebsiteContent)
    mock_resource.text_id = "f3d0ebae-7083-4524-9b93-f688537a0317"
    mock_resource.metadata = {"has_external_license_warning": True}

    mocker.patch(
        "websites.management.commands.markdown_cleaning.rules.link_to_external_resource.get_or_build_external_resource",
        return_value=mock_resource,
    )

    rule = LinkToExternalResourceRule()
    rule.set_options({"commit": False})

    mock_starter = mocker.Mock()
    mock_starter.slug = settings.OCW_COURSE_STARTER_SLUG
    rule.starter_lookup.get_starter = mocker.Mock(return_value=mock_starter)

    mock_toks = mocker.Mock()
    mock_toks.link.destination = "https://example.com"
    mock_toks.link.text = "Example Link"
    mock_toks.link.is_image = False
    mock_toks.original_text = "[Example Link](https://example.com)"

    # Call replace_match
    rule.replace_match("", 0, mock_toks, website_content)

    # Verify save was not called
    mock_resource.save.assert_not_called()
    mock_resource.referencing_content.add.assert_not_called()


def test_link_to_external_resource_no_save_when_commit_true(mocker):
    """Test that external resource is not saved when commit is True."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    mock_resource = mocker.Mock(spec=WebsiteContent)
    mock_resource.text_id = "f3d0ebae-7083-4524-9b93-f688537a0317"
    mock_resource.metadata = {"has_external_license_warning": True}

    mocker.patch(
        "websites.management.commands.markdown_cleaning.rules.link_to_external_resource.get_or_build_external_resource",
        return_value=mock_resource,
    )

    rule = LinkToExternalResourceRule()
    rule.set_options({"commit": True})

    mock_starter = mocker.Mock()
    mock_starter.slug = settings.OCW_COURSE_STARTER_SLUG
    rule.starter_lookup.get_starter = mocker.Mock(return_value=mock_starter)

    mock_toks = mocker.Mock()
    mock_toks.link.destination = "https://example.com"
    mock_toks.link.text = "Example Link"
    mock_toks.link.is_image = False
    mock_toks.original_text = "[Example Link](https://example.com)"

    # Call replace_match
    rule.replace_match("", 0, mock_toks, website_content)

    # Verify save was called
    mock_resource.save.assert_called_once()
    mock_resource.referencing_content.add.assert_called_once_with(website_content)


def test_navitem_to_external_resource_no_save_when_commit_false(mocker):
    """Test that external resource is not saved when commit is False."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    mock_resource = mocker.Mock(spec=WebsiteContent)
    mock_resource.text_id = "f3d0ebae-7083-4524-9b93-f688537a0317"  # Valid UUID
    mock_resource.metadata = {"has_external_license_warning": True}

    mocker.patch(
        "websites.management.commands.markdown_cleaning.rules.link_to_external_resource.build_external_resource",
        return_value=mock_resource,
    )

    rule = NavItemToExternalResourceRule()
    rule.set_options({"commit": False})

    nav_item = {
        "name": "Example Nav Item",
        "url": "https://example.com",
        "identifier": "external--123456789",
        "weight": 10,
    }

    # Call generate_item_replacement
    rule.generate_item_replacement(website_content, nav_item)

    # Verify save was not called
    mock_resource.save.assert_not_called()
    mock_resource.referencing_content.add.assert_not_called()


def test_navitem_to_external_resource_no_save_when_commit_true(mocker):
    """Test that external resource is saved when commit is True."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    mock_resource = mocker.Mock(spec=WebsiteContent)
    mock_resource.text_id = "f3d0ebae-7083-4524-9b93-f688537a0317"  # Valid UUID
    mock_resource.metadata = {"has_external_license_warning": True}

    mocker.patch(
        "websites.management.commands.markdown_cleaning.rules.link_to_external_resource.build_external_resource",
        return_value=mock_resource,
    )

    rule = NavItemToExternalResourceRule()
    rule.set_options({"commit": True})

    nav_item = {
        "name": "Example Nav Item",
        "url": "https://example.com",
        "identifier": "external--123456789",
        "weight": 10,
    }

    # Call generate_item_replacement
    rule.generate_item_replacement(website_content, nav_item)

    # Verify save was called
    mock_resource.save.assert_called_once()
    mock_resource.referencing_content.add.assert_called_once_with(website_content)


def test_navitem_transform_text_handles_internal_references_commit_true(mocker):
    """Test that transform_text properly handles internal nav item references when commit=True."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    # Create actual referenced content objects
    WebsiteContentFactory.create(
        website=website,
        text_id="f3d0ebae-7083-4524-9b93-f688537a0317",
        title="Referenced Page 1",
    )
    WebsiteContentFactory.create(
        website=website,
        text_id="a1b2c3d4-5678-9012-3456-789012345678",
        title="Referenced Page 2",
    )

    rule = NavItemToExternalResourceRule()
    rule.set_options({"commit": True})

    # Test data with only internal references (no external links)
    nav_items = [
        {
            "name": "Internal Reference 1",
            "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317",
            "weight": 20,
        },
        {
            "name": "Internal Reference 2",
            "identifier": "a1b2c3d4-5678-9012-3456-789012345678",
            "weight": 30,
        },
        {
            "name": "No Identifier",
            "weight": 40,
        },
    ]

    # Mock on_match callback
    mock_on_match = mocker.Mock()

    # Call transform_text
    result = rule.transform_text(website_content, nav_items, mock_on_match)

    # Verify the result structure - nav items should be unchanged
    assert isinstance(result, list)
    assert len(result) == 3
    # Cast to dict for type checking
    result_items = [item for item in result if isinstance(item, dict)]
    assert len(result_items) == 3
    assert result_items[0].get("identifier") == "f3d0ebae-7083-4524-9b93-f688537a0317"
    assert result_items[1].get("identifier") == "a1b2c3d4-5678-9012-3456-789012345678"
    assert "identifier" not in result_items[2]


def test_navitem_transform_text_handles_internal_references_commit_false(mocker):
    """Test that transform_text does not set references when commit=False."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    rule = NavItemToExternalResourceRule()
    rule.set_options({"commit": False})

    # Test data with internal references
    nav_items = [
        {
            "name": "Internal Reference 1",
            "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317",
            "weight": 20,
        },
        {
            "name": "Internal Reference 2",
            "identifier": "a1b2c3d4-5678-9012-3456-789012345678",
            "weight": 30,
        },
    ]

    # Mock on_match callback
    mock_on_match = mocker.Mock()

    # Call transform_text
    result = rule.transform_text(website_content, nav_items, mock_on_match)

    # Verify the nav items are returned unchanged
    assert result == nav_items


def test_navitem_transform_text_mixed_external_and_internal_references(mocker):
    """Test transform_text with mix of external links and internal references."""
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    website_content = WebsiteContentFactory.create(website=website)

    # Create actual referenced content
    WebsiteContentFactory.create(
        website=website,
        text_id="f3d0ebae-7083-4524-9b93-f688537a0317",
        title="Referenced Page",
    )

    rule = NavItemToExternalResourceRule()
    rule.set_options({"commit": True})

    # Test data with mix of external and internal
    nav_items = [
        {
            "name": "External Link",
            "url": "https://example.com",
            "identifier": "external--123456789",
            "weight": 10,
        },
        {
            "name": "Internal Reference",
            "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317",
            "weight": 20,
        },
    ]

    # Mock the external resource creation
    mock_external_resource = mocker.Mock(spec=WebsiteContent)
    mock_external_resource.text_id = "b2c3d4e5-6789-0123-4567-890123456789"
    mock_external_resource.metadata = {"has_external_license_warning": True}

    mocker.patch.object(
        rule,
        "generate_item_replacement",
        return_value=(
            {
                "name": "External Link",
                "identifier": "b2c3d4e5-6789-0123-4567-890123456789",
                "weight": 10,
            },
            mock_external_resource,
        ),
    )

    # Mock on_match callback
    mock_on_match = mocker.Mock()

    result = rule.transform_text(website_content, nav_items, mock_on_match)

    assert isinstance(result, list)
    assert len(result) == 2

    result_items = [item for item in result if isinstance(item, dict)]
    assert len(result_items) == 2

    # First item should be the transformed external link
    assert result_items[0].get("identifier") == "b2c3d4e5-6789-0123-4567-890123456789"
    # Second item should be unchanged internal reference
    assert result_items[1].get("identifier") == "f3d0ebae-7083-4524-9b93-f688537a0317"


def test_navitem_internal_references_functionality():
    """Test that internal nav item references properly set the referenced_by relationship."""
    with patch(
        "external_resources.signals.submit_url_to_wayback_task.delay", return_value=None
    ):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)

        main_content = WebsiteContentFactory.create(website=website)

        referenced_content_1 = WebsiteContentFactory.create(
            website=website,
            text_id="f3d0ebae-7083-4524-9b93-f688537a0317",
            title="Referenced Page 1",
        )
        referenced_content_2 = WebsiteContentFactory.create(
            website=website,
            text_id="a1b2c3d4-5678-9012-3456-789012345678",
            title="Referenced Page 2",
        )

        # Create nav items that reference these content objects
        nav_items = [
            {
                "name": "Link to Page 1",
                "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317",
                "weight": 10,
            },
            {
                "name": "Link to Page 2",
                "identifier": "a1b2c3d4-5678-9012-3456-789012345678",
                "weight": 20,
            },
            {
                "name": "External Link",
                "url": "https://example.com",
                "identifier": "external--123456789",
                "weight": 30,
            },
        ]

        # Set the nav items on the main content
        main_content.metadata = {"leftnav": nav_items}
        main_content.save()

        # Use the cleaner to process the nav items
        cleaner = get_cleaner("nav_item")
        cleaner.update_website_content(main_content)

        # Refresh from database to get updated relationships
        main_content.refresh_from_db()
        referenced_content_1.refresh_from_db()
        referenced_content_2.refresh_from_db()

        # Verify that the referenced content objects now have main_content in their referencing_content
        assert main_content in referenced_content_1.referencing_content.all()
        assert main_content in referenced_content_2.referencing_content.all()

        # Verify that an external resource was created for the external link
        external_resources = WebsiteContent.objects.filter(
            website=website, type=CONTENT_TYPE_EXTERNAL_RESOURCE
        )
        assert external_resources.count() == 1
        external_resource = external_resources.first()
        assert external_resource.metadata["external_url"] == "https://example.com"

        # Verify that the external resource references the main content
        assert main_content in external_resource.referencing_content.all()


@pytest.mark.parametrize(
    ("url", "has_external_license_warning", "expected_warning"),
    [
        # When parameter is True: force warning for all domains
        ("https://ocw.mit.edu", True, True),
        ("https://example.com", True, True),
        # When parameter is False: force no warning for all domains
        ("https://ocw.mit.edu", False, False),
        ("https://example.com", False, False),
        # When parameter is None: use hostname-based logic
        ("https://ocw.mit.edu", None, False),
        ("https://example.com", None, True),
    ],
)
@patch("django.conf.settings.SITEMAP_DOMAIN", "ocw.mit.edu")
def test_build_external_resource_with_license_warning_override(
    url, has_external_license_warning, expected_warning
):
    """Test build_external_resource respects has_external_license_warning override.

    When has_external_license_warning=True, it forces the warning regardless of domain.
    When has_external_license_warning=False, it forces no warning regardless of domain.
    When has_external_license_warning=None, it uses hostname-based logic.
    """
    starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    title = "Test Resource"

    external_resource = build_external_resource(
        website=website,
        site_config=SiteConfig(SAMPLE_SITE_CONFIG),
        title=title,
        url=url,
        has_external_license_warning=has_external_license_warning,
    )

    assert (
        external_resource.metadata["has_external_license_warning"] == expected_warning
    )


@pytest.mark.parametrize(
    ("url", "has_external_license_warning", "expected_warning"),
    [
        # When parameter is True: force warning for all domains
        ("https://ocw.mit.edu", True, True),
        ("https://example.com", True, True),
        # When parameter is False: force no warning for all domains
        ("https://ocw.mit.edu", False, False),
        ("https://example.com", False, False),
        # When parameter is None: use hostname-based logic
        ("https://ocw.mit.edu", None, False),
        ("https://example.com", None, True),
    ],
)
@patch("django.conf.settings.SITEMAP_DOMAIN", "ocw.mit.edu")
def test_link_to_external_resource_rule_with_license_warning_override(
    settings, url, has_external_license_warning, expected_warning
):
    """Test LinkToExternalResourceRule respects has_external_license_warning option.

    When True, forces warning regardless of domain.
    When False, forces no warning regardless of domain.
    When None, uses hostname-based logic (OCW domain = no warning, external domain = warning).
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Extract domain name for link text
        content = f"[{urlparse(url).netloc}]({url})"
        target_content = WebsiteContentFactory.create(
            markdown=content,
            website=website,
        )

        rule = LinkToExternalResourceRule()
        rule.set_options(
            {
                "commit": True,
                "has_external_license_warning": has_external_license_warning,
            }
        )
        cleaner = Cleaner(rule)
        cleaner.update_website_content(target_content)

        external_resource = WebsiteContent.objects.get(
            website=website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
            metadata__external_url=url,
        )

        assert (
            external_resource.metadata["has_external_license_warning"]
            == expected_warning
        )


@pytest.mark.parametrize(
    ("url", "has_external_license_warning", "expected_warning"),
    [
        # When parameter is True: force warning for all domains
        ("https://ocw.mit.edu", True, True),
        ("https://example.com", True, True),
        # When parameter is False: force no warning for all domains
        ("https://ocw.mit.edu", False, False),
        ("https://example.com", False, False),
        # When parameter is None: use hostname-based logic
        ("https://ocw.mit.edu", None, False),
        ("https://example.com", None, True),
    ],
)
@patch("django.conf.settings.SITEMAP_DOMAIN", "ocw.mit.edu")
def test_nav_item_to_external_resource_rule_with_license_warning_override(
    url, has_external_license_warning, expected_warning
):
    """Test NavItemToExternalResourceRule respects has_external_license_warning option.

    When True, forces warning regardless of domain.
    When False, forces no warning regardless of domain.
    When None, uses hostname-based logic (OCW domain = no warning, external domain = warning).
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)

        # Extract domain name for nav item name
        nav_items = [
            {
                "name": urlparse(url).netloc,
                "url": url,
                "weight": 10,
                "identifier": "external--test-id",
            }
        ]

        target_content = WebsiteContentFactory.create(
            website=website,
            metadata={"leftnav": nav_items},
        )

        rule = NavItemToExternalResourceRule()
        rule.set_options(
            {
                "commit": True,
                "has_external_license_warning": has_external_license_warning,
            }
        )
        cleaner = Cleaner(rule)
        cleaner.update_website_content(target_content)

        external_resource = WebsiteContent.objects.get(
            website=website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
            metadata__external_url=url,
        )

        assert (
            external_resource.metadata["has_external_license_warning"]
            == expected_warning
        )


@pytest.mark.django_db
def test_link_to_external_resource_skips_shortcode_attributes(settings):
    """Test that links inside Hugo shortcode attributes are not converted."""
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(
            config=SAMPLE_SITE_CONFIG,
        )
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Test case: link inside shortcode attribute should NOT be converted
        markdown_with_shortcode_link = """
            {{< image-gallery >}}
            {{< image-gallery-item href="test1.png" text="Botryoidal and massive hematite: Fe{{< sub 2 >}}O{{< sub 3 >}}." >}}
            {{< image-gallery-item href="test1.png" data-ngdesc="An end view diagram of the Beaver press with various parts identified." text="[OCW](https://ocw.mit.edu) - The screw to which the bar of the press is affixed, and which produces the pressure on the platen." >}}
            {{< /image-gallery >}}
        """

        # Test case: regular link should be converted
        markdown_with_regular_link = (
            "Here is a [regular link](https://example.com) that should be converted."
        )

        # Test case: mixed content - regular links converted, shortcode links preserved
        markdown_mixed = f"""
            Here is a [normal link](https://example.com).
            {markdown_with_shortcode_link}
            And another [normal link](https://example2.com) here.
        """

        website_content_shortcode = WebsiteContentFactory.create(
            website=website, markdown=markdown_with_shortcode_link, type="page"
        )

        website_content_regular = WebsiteContentFactory.create(
            website=website, markdown=markdown_with_regular_link, type="page"
        )

        website_content_mixed = WebsiteContentFactory.create(
            website=website, markdown=markdown_mixed, type="page"
        )

        rule = LinkToExternalResourceRule()
        rule.set_options({"commit": True})
        cleaner = Cleaner(rule)

        # Test 1: Shortcode attribute link should NOT be converted
        original_shortcode_content = website_content_shortcode.markdown
        cleaner.update_website_content(website_content_shortcode)

        # The content should remain unchanged (link inside shortcode attribute preserved)
        assert website_content_shortcode.markdown == original_shortcode_content
        assert "[OCW](https://ocw.mit.edu)" in website_content_shortcode.markdown
        assert "resource_link" not in website_content_shortcode.markdown

        # Test 2: Regular link should be converted
        updated_regular = cleaner.update_website_content(website_content_regular)
        assert updated_regular is True
        assert "resource_link" in website_content_regular.markdown
        assert (
            "[regular link](https://example.com)"
            not in website_content_regular.markdown
        )

        # Test 3: Mixed content - only regular links converted
        updated_mixed = cleaner.update_website_content(website_content_mixed)
        assert updated_mixed is True
        # Regular links should be converted
        assert (
            "[normal link](https://example.com)" not in website_content_mixed.markdown
        )
        assert (
            "[normal link](https://example2.com)" not in website_content_mixed.markdown
        )
        assert "resource_link" in website_content_mixed.markdown
        # Shortcode attribute link should be preserved
        assert "[OCW](https://ocw.mit.edu)" in website_content_mixed.markdown


@pytest.mark.parametrize(
    ("markdown_text", "should_convert", "description"),
    [
        # Link after closed shortcode should be converted
        (
            "Before {{< shortcode >}} and [link](https://example.com) after",
            True,
            "after closed shortcode",
        ),
        # Link inside single-line shortcode attribute should NOT be converted
        (
            '{{< image-gallery-item text="[link](https://example.com)" >}}',
            False,
            "single-line shortcode attribute",
        ),
        # Link with multiple attributes should NOT be converted
        (
            '{{< image-gallery-item text="Some [link](https://example.com) text" attr="value" >}}',
            False,
            "multiple attributes",
        ),
        # Multiple links inside same shortcode attribute should NOT be converted
        (
            '{{< image-gallery-item text="Check [link1](https://example.com) and [link2](https://google.com) both" >}}',
            False,
            "multiple links in single attribute",
        ),
        # Link outside any shortcode should be converted
        ("Regular [link](https://example.com) in text", True, "outside shortcode"),
    ],
)
@pytest.mark.django_db
def test_shortcode_attribute_detection_edge_cases(
    settings, markdown_text, should_convert, description
):
    """Test edge cases for shortcode attribute detection."""
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(
            config=SAMPLE_SITE_CONFIG,
        )
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        website_content = WebsiteContentFactory.create(
            website=website, markdown=markdown_text, type="page"
        )

        rule = LinkToExternalResourceRule()
        rule.set_options({"commit": True})
        cleaner = Cleaner(rule)

        original_content = website_content.markdown
        updated = cleaner.update_website_content(website_content)

        if should_convert:
            assert updated is True, (
                f"Failed: {description} - should have been converted"
            )
            assert "resource_link" in website_content.markdown, (
                f"Failed: {description} - no resource_link found"
            )
            # Check that original markdown links are no longer present
            assert "](https://" not in website_content.markdown, (
                f"Failed: {description} - original links still present"
            )
        else:
            # Content should remain unchanged
            assert website_content.markdown == original_content, (
                f"Failed: {description} - content was modified"
            )
            # Check that original markdown links are still present
            assert "](https://" in website_content.markdown, (
                f"Failed: {description} - original links missing"
            )
            assert "resource_link" not in website_content.markdown, (
                f"Failed: {description} - unexpected resource_link found"
            )
