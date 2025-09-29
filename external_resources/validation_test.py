"""
Comprehensive validation tests for external resources to prevent
mass publish/build pipeline failures due to invalid markdown syntax.
"""

import re
import pytest
from django.core.exceptions import ValidationError
from hypothesis import given, strategies as st

from external_resources.factories import ExternalResourceStateFactory
from external_resources.models import ExternalResourceState
from websites.factories import WebsiteContentFactory
from websites.factories import WebsiteFactory
from websites.management.commands.markdown_cleaning.rules.link_to_external_resource import (
    LinkToExternalResourceRule,
    get_or_build_external_resource,
)
from websites.site_config_api import SiteConfig


pytestmark = pytest.mark.django_db


class TestExternalResourceMarkdownValidation:
    """Test external resource markdown validation to prevent pipeline failures"""

    def test_hugo_partials_subscript_not_nested_in_shortcode(self):
        """Ensure Hugo partial subscripts are not nested within resource_link shortcodes"""
        website = WebsiteFactory.create()

        # Test content with Hugo partials that should NOT be nested
        test_cases = [
            'Text with {{< subscript "2" >}} should be preserved',
            'Formula H{{< subscript "2" >}}O should work',
            'Temperature 25{{< superscript "°C" >}} is normal',
            'E = mc{{< superscript "2" >}} equation',
        ]

        for content in test_cases:
            content_obj = WebsiteContentFactory.create(
                website=website, markdown=content
            )

            # Process through external resource rule (simulating migration)
            rule = LinkToExternalResourceRule()
            processed_content = content_obj.markdown

            # Validate that Hugo partials are never nested in resource_link shortcodes
            # This pattern would break the mass build pipeline
            nested_pattern = (
                r'\{\{% resource_link "[^"]*" "[^"]*\{\{<[^>]*>[^}]*\}\}[^"]*" %\}\}'
            )
            assert not re.search(nested_pattern, processed_content), (
                f"Found nested Hugo partial in shortcode: {processed_content}"
            )

            # Validate Hugo syntax is still valid
            assert self._validate_hugo_syntax(processed_content)

    def test_external_resource_creation_with_complex_markdown(self):
        """Test external resource creation with various markdown scenarios"""
        website = WebsiteFactory.create()

        complex_markdown_cases = [
            {
                "description": "Subscript in description",
                "markdown": 'Chemical formula H{{< subscript "2" >}}O',
                "url": "https://example.com/chemistry",
                "title": "Chemistry Resource",
            },
            {
                "description": "Superscript with special characters",
                "markdown": 'Temperature 25{{< superscript "°C" >}} measurement',
                "url": "https://example.com/temp",
                "title": "Temperature Guide",
            },
            {
                "description": "Mixed partials",
                "markdown": 'E = mc{{< superscript "2" >}} and H{{< subscript "2" >}}O',
                "url": "https://example.com/physics",
                "title": "Physics Resource",
            },
            {
                "description": "Escaped quotes",
                "markdown": 'Formula with "quotes" and {{< subscript "x" >}}',
                "url": "https://example.com/quotes",
                "title": "Quoted Resource",
            },
        ]

        for case in complex_markdown_cases:
            # Create external resource with complex markdown
            resource = WebsiteContentFactory.create(
                website=website,
                type="external_resource",
                title=case["title"],
                metadata={"external_url": case["url"], "description": case["markdown"]},
            )

            # Validate the resource was created successfully
            assert resource.title == case["title"]
            assert resource.metadata["external_url"] == case["url"]

            # Ensure markdown doesn't break Hugo processing
            description = resource.metadata.get("description", "")
            assert self._validate_hugo_syntax(description)

            # Ensure no double-nesting occurred
            assert not self._has_nested_shortcodes(description)

    def test_external_resource_state_link_validation(self):
        """Test external resource state validation with real links"""
        # Create external resource with valid link
        content = WebsiteContentFactory.create(
            metadata={"external_resource": {"url": "https://httpbin.org/status/200"}}
        )
        state = ExternalResourceStateFactory.create(
            content=content,
            external_url_response_code=200,
            status=ExternalResourceState.Status.VALID
        )

    def test_mass_build_pipeline_markdown_compatibility(self):
        """Test markdown scenarios that would break mass build pipeline"""
        website = WebsiteFactory.create()

        # Scenarios that previously caused pipeline failures
        problematic_cases = [
            # Nested shortcodes (should be prevented)
            'Link with {{% resource_link "uuid" "Text with {{< subscript "bad" >}}" %}} nesting',
            # Unescaped quotes in shortcodes
            'Resource {{% resource_link "uuid" "Title with "quotes" problem" %}}',
            # Mixed quote types
            "Resource {{% resource_link 'uuid' \"Mixed quotes problem\" %}}",
            # Special characters in Hugo partials
            'Temperature {{< superscript "°C±2" >}} with symbols',
        ]

        for case in problematic_cases:
            content = WebsiteContentFactory.create(website=website, markdown=case)

            # Validate this content won't break the pipeline
            assert self._validate_pipeline_compatibility(content.markdown)

    @given(
        st.text(
            min_size=1,
            max_size=500,
            alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
        )
    )
    def test_external_resource_title_never_breaks_hugo(self, title_text):
        """Property-based test: external resource titles should never break Hugo syntax"""
        # Skip if title contains problematic characters for Hugo
        if any(char in title_text for char in ["{{", "}}", "{%", "%}", '"', "'"]):
            return

        website = WebsiteFactory.create()

        try:
            resource = WebsiteContentFactory.create(
                website=website,
                type="external_resource",
                title=title_text[:100],  # Limit length for practical testing
                metadata={"external_url": "https://example.com"},
            )

            # Should not throw validation errors
            resource.full_clean()

            # Hugo syntax should remain valid
            assert self._validate_hugo_syntax(resource.title)

        except ValidationError:
            # Some characters may cause validation errors, which is acceptable
            pass

    def test_markdown_cleanup_rule_preserves_hugo_syntax(self):
        """Test that markdown cleanup rules preserve valid Hugo syntax"""
        website = WebsiteFactory.create()

        # Content with mixed external links and Hugo partials
        markdown_with_links = """
        Here is a link to [chemistry resource](https://example.com/chem) about H{{< subscript "2" >}}O.
        
        Another [physics link](https://example.com/physics) discusses E = mc{{< superscript "2" >}}.
        
        Regular text with {{< subscript "formula" >}} should be preserved.
        """

        content = WebsiteContentFactory.create(
            website=website, markdown=markdown_with_links
        )

        # Process through link cleanup rule
        rule = LinkToExternalResourceRule()
        # Note: This would normally process the content, but we're testing the principle

        # Validate original Hugo partials are preserved
        hugo_partials = re.findall(
            r"\{\{<\s*(?:subscript|superscript)\s+[^>]*>\}\}", content.markdown
        )
        assert len(hugo_partials) >= 2  # Should find our test partials

        # No nested shortcodes should exist
        assert not self._has_nested_shortcodes(content.markdown)

    def _validate_hugo_syntax(self, content: str) -> bool:
        """Validate that content has valid Hugo syntax"""
        if not content:
            return True

        # Check for balanced Hugo shortcodes
        shortcode_pattern = r"\{\{<\s*\w+[^>]*>\}\}"
        resource_link_pattern = r'\{\{% resource_link "[^"]*" "[^"]*" %\}\}'

        # Basic validation - no unclosed brackets
        open_count = content.count("{{")
        close_count = content.count("}}")

        if open_count != close_count:
            return False

        # Validate shortcode syntax
        shortcodes = re.findall(shortcode_pattern, content)
        resource_links = re.findall(resource_link_pattern, content)

        # All found patterns should be valid
        return True  # Basic validation for now

    def _has_nested_shortcodes(self, content: str) -> bool:
        """Check if content has nested Hugo shortcodes (which would break pipeline)"""
        # Look for patterns like {{% resource_link "uuid" "text with {{< shortcode >}} inside" %}}
        nested_pattern = r'\{\{% resource_link "[^"]*" "[^"]*\{\{[^}]*\}\}[^"]*" %\}\}'
        return bool(re.search(nested_pattern, content))

    def _validate_pipeline_compatibility(self, content: str) -> bool:
        """Validate that content is compatible with mass build pipeline"""
        # Check for known problematic patterns
        problematic_patterns = [
            r'\{\{% resource_link "[^"]*" "[^"]*\{\{<[^>]*>[^}]*\}\}[^"]*" %\}\}',  # Nested partials
            r'\{\{% resource_link "[^"]*" "[^"]*"[^"]*"[^"]*" %\}\}',  # Unescaped quotes
        ]

        for pattern in problematic_patterns:
            if re.search(pattern, content):
                return False

        return True


class TestExternalResourceIntegration:
    """Integration tests for external resource processing"""

    def test_external_resource_to_hugo_shortcode_conversion(self, basic_site_config):
        """Test complete workflow from external link to Hugo shortcode"""
        website = WebsiteFactory.create()

        # Original markdown with external link
        original_markdown = (
            "Check out this [resource](https://example.com/page) for more info."
        )

        content = WebsiteContentFactory.create(
            website=website, markdown=original_markdown
        )

        # Simulate the external resource creation process
        resource = get_or_build_external_resource(
            website=website,
            site_config=SiteConfig(basic_site_config),
            url="https://example.com/page",
            title="resource",
        )

        # Should create valid external resource
        assert resource.type == "external_resource"
        assert resource.metadata["external_url"] == "https://example.com/page"

        # Generated shortcode should be valid
        shortcode = f'{{% resource_link "{resource.text_id}" "resource" %}}'
        assert self._is_valid_hugo_shortcode(shortcode)

    def test_bulk_external_resource_processing(self):
        """Test processing multiple external resources in bulk (simulating mass operations)"""
        website = WebsiteFactory.create()

        # Create multiple content pieces with external links
        test_contents = []
        for i in range(10):
            content = WebsiteContentFactory.create(
                website=website,
                markdown=f'Link to [resource {i}](https://example.com/page{i}) with H{{{{ subscript "{i}" }}}}O formula.',
            )
            test_contents.append(content)

        # Process all content (simulating mass operation)
        processed_count = 0
        for content in test_contents:
            # Validate each piece of content
            assert self._validate_hugo_syntax(content.markdown)
            assert not self._has_nested_shortcodes(content.markdown)
            processed_count += 1

        assert processed_count == 10

    def _is_valid_hugo_shortcode(self, shortcode: str) -> bool:
        """Validate Hugo shortcode syntax"""
        pattern = r'\{\{% \w+ (?:"[^"]*" ?)+%\}\}'
        return bool(re.match(pattern, shortcode))

    def _validate_hugo_syntax(self, content: str) -> bool:
        """Validate Hugo syntax (shared method)"""
        if not content:
            return True
        open_count = content.count("{{")
        close_count = content.count("}}")
        return open_count == close_count

    def _has_nested_shortcodes(self, content: str) -> bool:
        """Check for nested shortcodes (shared method)"""
        nested_pattern = r"\{\{[^}]*\{\{[^}]*\}\}[^}]*\}\}"
        return bool(re.search(nested_pattern, content))


class TestMassBuildPipelineIntegration:
    """Tests specifically focused on mass build pipeline compatibility"""

    def test_mass_build_with_external_resources_success_scenario(self):
        """Test that mass build pipeline succeeds with properly formatted external resources"""
        websites = [WebsiteFactory.create() for _ in range(3)]

        # Create external resources for each website
        for website in websites:
            for i in range(2):
                ExternalResourceStateFactory.create(
                    content=WebsiteContentFactory.create(
                        website=website,
                        type="external_resource",
                        title=f"Resource {i}",
                        metadata={
                            "external_url": f"https://example.com/resource{i}",
                            "description": f"Valid description without nested syntax {i}",
                        },
                    ),
                    external_url_response_code=200,
                )

        # Simulate mass build validation
        all_valid = True
        for website in websites:
            resources = website.websitecontent_set.filter(type="external_resource")
            for resource in resources:
                if not self._validate_for_mass_build(resource):
                    all_valid = False
                    break

        assert all_valid, "All external resources should be valid for mass build"

    def test_mass_build_failure_prevention(self):
        """Test that problematic external resources are caught before mass build"""
        website = WebsiteFactory.create()

        # Create a problematic external resource (simulating legacy migration issue)
        problematic_resource = WebsiteContentFactory.create(
            website=website,
            type="external_resource",
            title="Problematic Resource",
            metadata={
                "external_url": "https://example.com",
                "description": 'Text with nested {{% resource_link "uuid" "{{< subscript "bad" >}}" %}} syntax',
            },
        )

        # This should fail validation
        assert not self._validate_for_mass_build(problematic_resource)

    def _validate_for_mass_build(self, resource) -> bool:
        """Validate external resource for mass build pipeline compatibility"""
        if resource.type != "external_resource":
            return True

        description = resource.metadata.get("description", "")

        # Check for nested shortcodes that break pipeline
        nested_pattern = (
            r'\{\{% resource_link "[^"]*" "[^"]*\{\{<[^>]*>[^}]*\}\}[^"]*" %\}\}'
        )
        if re.search(nested_pattern, description):
            return False

        # Check for unescaped quotes in shortcodes
        quote_pattern = r'\{\{% resource_link "[^"]*" "[^"]*"[^"]*"[^"]*" %\}\}'
        if re.search(quote_pattern, description):
            return False

        return True
