"""Tests for link_resolveuid.py"""

from unittest.mock import patch

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


@pytest.mark.django_db()
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

    content_ids = {
        "nest-id": WebsiteContent.objects.get(title="Nest").text_id,
        "bird-1-id": WebsiteContent.objects.get(title="Bird 1").text_id,
        "bird-2-id": WebsiteContent.objects.get(title="Bird 2").text_id,
        "egg-id": WebsiteContent.objects.get(title="Egg").text_id,
    }

    # replace placeholders in the templates with new ids.
    expected_content = expected_content_template
    for item in expected_content:
        if item["name"] == "Control":
            continue

        item["identifier"] = content_ids[item["identifier"]]
        if item.get("parent"):
            item["parent"] = content_ids[item["parent"]]

    assert target_content.metadata["leftnav"] == expected_content


def test_rules_default_commit_value():
    """Test that both rules properly handle options when set."""
    link_rule = LinkToExternalResourceRule()
    nav_rule = NavItemToExternalResourceRule()

    # Set options using the inherited method
    link_rule.set_options({"commit": True})
    nav_rule.set_options({"commit": True})

    # Verify options are set correctly
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
