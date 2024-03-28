"""Tests for link_resolveuid.py"""
import pytest

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

EXAMPLE_RESOLVEUID = "89ce47d27edcdd9b8a8cbe641a59b520"
EXAMPLE_RESOLVEUID_FORMATTED = "89ce47d2-7edc-dd9b-8a8c-be641a59b520"


SITE_CONFIG = {
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
                {
                    "default": None,
                    "help": "Whether or not this link is broken.",
                    "label": "Is Broken",
                    "name": "is_broken",
                    "required": True,
                    "widget": "hidden",
                },
                {
                    "default": None,
                    "help": "URL to use when is_broken is true.",
                    "label": "Internet Archive Backup URL",
                    "name": "backup_url",
                    "required": True,
                    "widget": "hidden",
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
    starter = WebsiteStarterFactory.create(config=SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    title = "title"
    url = "https://google.com"

    external_resource = build_external_resource(
        website=website, site_config=SiteConfig(SITE_CONFIG), title=title, url=url
    )

    assert external_resource.title == title
    assert external_resource.metadata["external_url"] == url
    assert external_resource.metadata["has_external_license_warning"] is True
    assert not bool(external_resource.metadata["is_broken"])
    assert not bool(external_resource.metadata["backup_url"])


@pytest.mark.parametrize("content_exists", [True, False])
def test_get_or_build_external_resource(content_exists):
    """Test get_or_build_external_resource builds or gets depending on content existence."""
    starter = WebsiteStarterFactory.create(config=SITE_CONFIG)
    website = WebsiteFactory.create(starter=starter)
    title = "title"
    url = "https://google.com"
    site_config = SiteConfig(SITE_CONFIG)
    config_item = site_config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)

    if content_exists:
        existing_content = WebsiteContentFactory.create(
            metadata={
                "external_url": url,
                "has_external_license_warning": True,
                "is_broken": False,
                "backup_url": None,
            },
            dirpath=config_item.file_target,
            website=website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
            title=title,
        )

    external_resource = get_or_build_external_resource(
        website=website, site_config=SiteConfig(SITE_CONFIG), title=title, url=url
    )

    assert external_resource.title == title
    assert external_resource.metadata["external_url"] == url
    assert external_resource.metadata["has_external_license_warning"] is True
    assert not bool(external_resource.metadata["is_broken"])
    assert not bool(external_resource.metadata["backup_url"])

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
    starter = WebsiteStarterFactory.create(config=SITE_CONFIG)
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
    starter = WebsiteStarterFactory.create(config=SITE_CONFIG)
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
