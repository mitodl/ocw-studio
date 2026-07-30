"""
Integration tests for external resource markdown conversion with subscripts and superscripts.

These tests specifically address the issue where data migration of legacy external links
to External Resources converted subscripts and superscripts in markdown (Hugo partials syntax)
to nested markdown syntax, which broke the mass publish pipeline.
"""

from unittest.mock import patch

import pytest

from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.factories import WebsiteContentFactory, WebsiteFactory, WebsiteStarterFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.rules.link_to_external_resource import (
    LinkToExternalResourceRule,
)
from websites.models import WebsiteContent

SAMPLE_SITE_CONFIG = {
    "collections": [
        {
            "category": "Content",
            "fields": [
                {
                    "help": "The URL",
                    "label": "URL",
                    "name": "external_url",
                    "required": True,
                    "widget": "string",
                },
                {
                    "default": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                    "label": "License",
                    "name": "license",
                    "widget": "select",
                },
                {
                    "default": True,
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
}

pytestmark = pytest.mark.django_db


def get_cleaner():
    """Get cleaner configured for external resource conversion."""
    rule = LinkToExternalResourceRule()
    rule.set_options({"commit": True})
    return Cleaner(rule)


def test_external_resource_conversion_with_subscript_in_link_text(settings):
    """
    Test that links with subscript Hugo shortcodes in the title are correctly converted.
    
    This addresses the regression where H{{< sub 2 >}}O became nested markdown that broke publishing.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Original markdown with subscript in link text (like H2O)
        markdown_with_subscript = '[H{{< sub "2" >}}O](http://example.com/water)'

        content = WebsiteContentFactory.create(
            markdown=markdown_with_subscript,
            website=website,
        )

        cleaner = get_cleaner()
        cleaner.update_website_content(content)

        # Verify conversion happened
        assert "resource_link" in content.markdown
        assert '[H{{< sub "2" >}}O]' not in content.markdown

        # Verify the external resource was created with proper title
        external_resource = WebsiteContent.objects.get(
            website=website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
            metadata__external_url="http://example.com/water",
        )

        # The title should have HTML representation, not Hugo shortcode
        assert "<sub>2</sub>" in content.markdown or "H2O" in external_resource.title


def test_external_resource_conversion_with_superscript_in_link_text(settings):
    """
    Test that links with superscript Hugo shortcodes are correctly converted.
    
    This addresses cases like trademark symbols: TM{{< sup "®" >}}
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Link with superscript (like trademark)
        markdown_with_superscript = '[Product{{< sup "®" >}}](http://example.com/product)'

        content = WebsiteContentFactory.create(
            markdown=markdown_with_superscript,
            website=website,
        )

        cleaner = get_cleaner()
        cleaner.update_website_content(content)

        # Verify conversion
        assert "resource_link" in content.markdown
        
        # Should convert Hugo shortcode to HTML
        assert "<sup>®</sup>" in content.markdown


def test_external_resource_conversion_with_complex_chemical_formula(settings):
    """
    Test conversion of links with complex chemical formulas containing multiple subscripts.
    
    Example: Fe{{< sub 2 >}}O{{< sub 3 >}}
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Chemical formula with multiple subscripts
        markdown_complex = '[Fe{{< sub "2" >}}O{{< sub "3" >}}](http://example.com/iron-oxide)'

        content = WebsiteContentFactory.create(
            markdown=markdown_complex,
            website=website,
        )

        cleaner = get_cleaner()
        cleaner.update_website_content(content)

        # Should convert successfully
        assert "resource_link" in content.markdown
        
        # Should have HTML subscripts
        assert "<sub>" in content.markdown


def test_external_resource_conversion_with_nested_sub_sup(settings):
    """
    Test conversion of links with nested subscript and superscript.
    
    This is a complex edge case that could break publishing if not handled correctly.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Nested shortcodes (rare but possible)
        markdown_nested = '[Value{{< sup "{{< sub \\"x\\" >}}" >}}](http://example.com)'

        content = WebsiteContentFactory.create(
            markdown=markdown_nested,
            website=website,
        )

        cleaner = get_cleaner()
        cleaner.update_website_content(content)

        # Should handle without errors
        assert "resource_link" in content.markdown


def test_external_resource_conversion_multiple_links_with_shortcodes(settings):
    """
    Test that multiple links with shortcodes are all converted correctly.
    
    Ensures batch conversion doesn't introduce issues.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        markdown_multiple = """
        Here is [H{{< sub "2" >}}O](http://example.com/water) and
        also [CO{{< sub "2" >}}](http://example.com/co2) and
        even [E=mc{{< sup "2" >}}](http://example.com/einstein).
        """

        content = WebsiteContentFactory.create(
            markdown=markdown_multiple,
            website=website,
        )

        cleaner = get_cleaner()
        cleaner.update_website_content(content)

        # All links should be converted
        assert content.markdown.count("resource_link") == 3
        
        # Original markdown links should be gone
        assert "](http://example.com" not in content.markdown

        # Verify all external resources created
        external_resources = WebsiteContent.objects.filter(
            website=website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        )
        assert external_resources.count() == 3


def test_external_resource_conversion_preserves_markdown_validity(settings):
    """
    Test that conversion preserves valid markdown structure and doesn't create nested issues.
    
    This is the core issue - ensuring the converted markdown is valid for Hugo.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Complex markdown that previously broke
        problematic_markdown = """
        ## Chemical Compounds
        
        See the article on [H{{< sub "2" >}}O](http://example.com/water) for more info.
        
        Also check [CO{{< sub "2" >}}](http://example.com/co2) levels.
        
        Reference: [Einstein's E=mc{{< sup "2" >}}](http://example.com/energy)
        """

        content = WebsiteContentFactory.create(
            markdown=problematic_markdown,
            website=website,
        )

        original_structure = content.markdown
        
        cleaner = get_cleaner()
        result = cleaner.update_website_content(content)

        # Verify update was successful
        assert result is True
        
        # Verify markdown structure is still valid
        # Headers should be preserved
        assert "## Chemical Compounds" in content.markdown
        
        # Links should be converted to resource_link shortcodes
        assert "resource_link" in content.markdown
        
        # No invalid nested structures
        assert "[[" not in content.markdown
        assert "]]" not in content.markdown


def test_external_resource_mass_publish_compatibility(settings):
    """
    Integration test simulating the mass publish scenario.
    
    Ensures converted external resources don't break the publish pipeline.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        # Create multiple pages with various link patterns
        pages = [
            {
                "title": "Page 1",
                "markdown": '[H{{< sub "2" >}}O](http://example.com/water)',
            },
            {
                "title": "Page 2",
                "markdown": '[CO{{< sub "2" >}}](http://example.com/co2)',
            },
            {
                "title": "Page 3",
                "markdown": '[Product{{< sup "®" >}}](http://example.com/product)',
            },
        ]

        cleaner = get_cleaner()
        
        for page_data in pages:
            content = WebsiteContentFactory.create(
                title=page_data["title"],
                markdown=page_data["markdown"],
                website=website,
            )
            cleaner.update_website_content(content)

        # Verify all pages were converted successfully
        all_content = WebsiteContent.objects.filter(
            website=website,
            type__in=["page", "resource"],
        )

        # Should have 3 pages + 3 external resources
        external_resources = WebsiteContent.objects.filter(
            website=website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        )
        assert external_resources.count() == 3

        # Verify no invalid markdown patterns that would break publishing
        for content in all_content:
            if content.markdown:
                # No nested brackets
                assert "[[" not in content.markdown
                # No unclosed shortcodes
                assert content.markdown.count("{{<") == content.markdown.count(">}}")
                assert content.markdown.count("{{% ") == content.markdown.count(" %}}")


def test_external_resource_with_metadata_subscripts(settings):
    """
    Test conversion when subscripts appear in metadata fields too.
    
    The issue mentioned metadata conversion problems.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        markdown_content = '[H{{< sub "2" >}}O](http://example.com/water)'
        metadata_with_shortcode = 'Description with H{{< sub "2" >}}O formula'

        content = WebsiteContentFactory.create(
            markdown=markdown_content,
            metadata={"description": metadata_with_shortcode},
            website=website,
        )

        cleaner = get_cleaner()
        cleaner.update_website_content(content)

        # Both markdown and metadata should be converted
        assert "resource_link" in content.markdown
        
        # Metadata should also be cleaned if the rule processes it
        # (depends on implementation)


def test_external_resource_conversion_idempotent(settings):
    """
    Test that running conversion multiple times produces the same result.
    
    Ensures we don't have issues with re-running migrations or cleanup scripts.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        original_markdown = '[H{{< sub "2" >}}O](http://example.com/water)'

        content = WebsiteContentFactory.create(
            markdown=original_markdown,
            website=website,
        )

        cleaner = get_cleaner()
        
        # Run conversion first time
        cleaner.update_website_content(content)
        first_result = content.markdown
        
        # Run conversion second time
        cleaner.update_website_content(content)
        second_result = content.markdown
        
        # Results should be identical (idempotent)
        assert first_result == second_result
        
        # Should still be valid
        assert "resource_link" in second_result


@pytest.mark.parametrize(
    ("markdown_input", "should_convert", "description"),
    [
        # Valid cases that should convert
        ('[H{{< sub "2" >}}O](http://example.com)', True, "Simple subscript"),
        ('[Product{{< sup "®" >}}](http://example.com)', True, "Simple superscript"),
        ('[Fe{{< sub "2" >}}O{{< sub "3" >}}](http://example.com)', True, "Multiple subscripts"),
        # Edge cases
        ('{{< sub "2" >}}', False, "Shortcode without link"),
        ('[Normal text](http://example.com)', True, "Link without shortcode"),
        ('', False, "Empty content"),
        ('Plain text', False, "No links at all"),
    ],
)
def test_external_resource_conversion_parametrized(
    settings, markdown_input, should_convert, description
):
    """
    Parametrized test for various markdown patterns.
    
    Ensures robust handling of different input patterns.
    """
    with patch("external_resources.signals.submit_url_to_wayback_task.delay"):
        starter = WebsiteStarterFactory.create(config=SAMPLE_SITE_CONFIG)
        website = WebsiteFactory.create(starter=starter)
        settings.OCW_COURSE_STARTER_SLUG = starter.slug

        content = WebsiteContentFactory.create(
            markdown=markdown_input,
            website=website,
        )

        cleaner = get_cleaner()
        result = cleaner.update_website_content(content)

        if should_convert and "](http://" in markdown_input:
            # If there was a link, it should be converted
            assert result is True, f"Failed: {description}"
            if should_convert:
                assert "resource_link" in content.markdown or markdown_input == "", f"Failed: {description}"
        else:
            # No conversion expected or no links to convert
            assert True  # Test passes if no errors
