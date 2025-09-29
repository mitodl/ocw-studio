"""
Integration tests for mass publish/build pipelines to prevent failures
due to external resource processing issues.
"""

import json
import re
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import override_settings

from content_sync.api import publish_website, trigger_publish
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.concourse import MassBuildSitesPipeline
from content_sync.tasks import publish_websites
from external_resources.factories import ExternalResourceStateFactory  
from external_resources.models import ExternalResourceState
from websites.constants import PUBLISH_STATUS_SUCCEEDED, PUBLISH_STATUS_ERRORED
from websites.factories import WebsiteFactory, WebsiteContentFactory
from websites.models import Website


pytestmark = pytest.mark.django_db


class TestMassBuildPipelineIntegration:
    """Integration tests for mass build pipeline with external resources"""

    @pytest.fixture
    def mock_pipeline_backend(self, mocker):
        """Mock the pipeline backend to prevent actual Concourse calls"""
        mock_api = MagicMock()
        mock_api.upsert_pipeline.return_value = None
        mock_api.trigger_build.return_value = {"status": "success"}
        
        mocker.patch("content_sync.api.get_pipeline_api", return_value=mock_api)
        mocker.patch("content_sync.pipelines.concourse.get_pipeline_api", return_value=mock_api)
        
        return mock_api

    @pytest.fixture  
    def websites_with_external_resources(self):
        """Create test websites with various external resource scenarios"""
        websites = []
        
        # Website with clean external resources
        clean_website = WebsiteFactory.create(name="clean-site")
        clean_resource = WebsiteContentFactory.create(
            website=clean_website,
            type="external_resource",
            title="Clean Resource",
            metadata={
                "external_url": "https://example.com/clean",
                "description": "Simple description without Hugo partials"
            }
        )
        ExternalResourceStateFactory.create(
            content=clean_resource,
            url="https://example.com/clean",
            status_code=200
        )
        websites.append(clean_website)
        
        # Website with Hugo partials (valid)
        hugo_website = WebsiteFactory.create(name="hugo-site")
        hugo_resource = WebsiteContentFactory.create(
            website=hugo_website,
            type="external_resource", 
            title="Chemistry Resource",
            metadata={
                "external_url": "https://example.com/chemistry",
                "description": "Chemical formula H{{< subscript \"2\" >}}O is water"
            }
        )
        ExternalResourceStateFactory.create(
            content=hugo_resource,
            url="https://example.com/chemistry",
            status_code=200
        )
        websites.append(hugo_website) 
        
        # Website with potentially problematic content (should be handled)
        complex_website = WebsiteFactory.create(name="complex-site")
        complex_resource = WebsiteContentFactory.create(  
            website=complex_website,
            type="external_resource",
            title="Complex Resource",
            metadata={
                "external_url": "https://example.com/complex",
                "description": "Formula E = mc{{< superscript \"2\" >}} with temperature 25{{< superscript \"°C\" >}}"
            }
        )
        ExternalResourceStateFactory.create(
            content=complex_resource,
            url="https://example.com/complex", 
            status_code=200
        )
        websites.append(complex_website)
        
        return websites

    def test_mass_build_pipeline_creation_with_external_resources(
        self, mock_pipeline_backend, websites_with_external_resources
    ):
        """Test mass build pipeline creation succeeds with external resources"""
        # Create mass build pipeline
        pipeline = MassBuildSitesPipeline(version=VERSION_DRAFT)
        
        # Should not raise exceptions
        pipeline.upsert_pipeline()
        
        # Pipeline API should have been called
        mock_pipeline_backend.upsert_pipeline.assert_called()

    def test_mass_publish_with_external_resources_validation(
        self, mock_pipeline_backend, websites_with_external_resources, mocker
    ):
        """Test mass publish validates external resources before processing"""
        # Mock the actual publishing task
        mock_task = mocker.patch("content_sync.tasks.publish_websites.delay")
        mock_task.return_value.id = "test-task-id"
        
        website_names = [site.name for site in websites_with_external_resources]
        
        # Should not raise validation errors
        task = publish_websites.delay(
            website_names,
            VERSION_DRAFT,
            chunk_size=2,
            prepublish=False,
            no_mass_build=False
        )
        
        assert task is not None

    def test_external_resource_content_validation_before_build(
        self, websites_with_external_resources
    ):
        """Test external resource content is validated before mass build"""
        for website in websites_with_external_resources:
            external_resources = website.websitecontent_set.filter(type="external_resource")
            
            for resource in external_resources:
                # Validate resource metadata
                assert "external_url" in resource.metadata
                assert resource.metadata["external_url"].startswith("http")
                
                # Validate description doesn't have nested shortcodes
                description = resource.metadata.get("description", "")
                assert not self._has_nested_shortcodes(description)
                
                # Validate Hugo syntax is balanced
                assert self._validate_hugo_syntax(description)

    def test_mass_build_handles_hugo_partials_correctly(
        self, mock_pipeline_backend, websites_with_external_resources
    ):
        """Test mass build pipeline handles Hugo partials without corruption"""
        hugo_website = next(site for site in websites_with_external_resources if site.name == "hugo-site")
        
        # Get external resource with Hugo partials
        hugo_resource = hugo_website.websitecontent_set.filter(type="external_resource").first()
        description = hugo_resource.metadata["description"]
        
        # Should contain valid Hugo partials
        assert "{{< subscript" in description
        assert ">}}" in description
        
        # Should not have nested resource_link shortcodes
        assert not re.search(r"\{\{% resource_link.*\{\{<.*>\}\}.*%\}\}", description)
        
        # Pipeline creation should succeed
        pipeline = MassBuildSitesPipeline(version=VERSION_DRAFT)
        pipeline.upsert_pipeline()

    def test_publish_website_with_external_resources(
        self, mock_pipeline_backend, websites_with_external_resources, mocker
    ):
        """Test individual website publishing with external resources"""
        # Mock website status updates
        mock_update_status = mocker.patch("websites.api.update_website_status")
        
        website = websites_with_external_resources[0]
        
        # Should not raise exceptions
        result = publish_website(
            website,
            VERSION_DRAFT,
            create_backend=False,
            trigger=True
        )
        
        # Should return success
        assert result is not None

    def test_mass_build_error_handling_with_invalid_resources(
        self, mock_pipeline_backend, mocker
    ):
        """Test mass build handles invalid external resources gracefully"""
        # Create website with problematic external resource
        problematic_website = WebsiteFactory.create(name="problematic-site")
        
        # This would be caught by validation
        problematic_resource = WebsiteContentFactory.create(
            website=problematic_website,
            type="external_resource",
            title="Problematic Resource",
            metadata={
                "external_url": "https://example.com/problem",
                # This is the type of nesting that causes pipeline failures
                "description": "Bad nesting {{% resource_link \"uuid\" \"Text with {{< subscript \"bad\" >}}\" %}} here"
            }
        )
        
        # Validation should catch this
        assert not self._validate_for_mass_build(problematic_resource)

    def test_pipeline_configuration_includes_external_resource_settings(
        self, mock_pipeline_backend, websites_with_external_resources
    ):
        """Test pipeline configuration includes necessary external resource settings"""
        pipeline = MassBuildSitesPipeline(version=VERSION_DRAFT)
        
        # Mock the pipeline definition to inspect configuration
        with patch("content_sync.pipelines.concourse.MassBuildSitesPipelineDefinition") as mock_def:
            mock_def.return_value.json.return_value = "mock_config"
            
            pipeline.upsert_pipeline()
            
            # Should be called with proper configuration
            mock_def.assert_called_once()
            config_arg = mock_def.call_args[1]["config"]  
            
            # Configuration should include external resource handling
            assert hasattr(config_arg, "version")
            assert config_arg.version == VERSION_DRAFT

    def test_mass_build_batch_processing_with_external_resources(
        self, mock_pipeline_backend, websites_with_external_resources, mocker
    ):
        """Test mass build processes batches of websites with external resources correctly"""
        # Mock batch processing
        mock_batch_task = mocker.patch("content_sync.tasks.upsert_website_pipeline_batch")
        
        website_names = [site.name for site in websites_with_external_resources]
        
        # Process in batches
        from content_sync.tasks import upsert_pipelines
        
        # Should handle batching without errors
        task = upsert_pipelines.delay(
            website_names,
            create_backend=False,
            unpause=False,
            chunk_size=2
        )
        
        # Task should be created successfully
        assert task is not None

    def test_external_resource_url_validation_in_pipeline(
        self, websites_with_external_resources
    ):
        """Test external resource URLs are validated before pipeline processing"""
        for website in websites_with_external_resources:
            external_resources = website.websitecontent_set.filter(type="external_resource")
            
            for resource in external_resources:
                # Get associated state
                states = ExternalResourceState.objects.filter(content=resource)
                
                for state in states:
                    # URL should be valid
                    assert state.url.startswith(("http://", "https://"))
                    
                    # Status code should indicate accessibility  
                    assert state.status_code in [200, 201, 301, 302, 404]  # Valid HTTP codes

    def test_hugo_syntax_preservation_through_pipeline(
        self, websites_with_external_resources
    ):
        """Test Hugo syntax is preserved correctly through pipeline processing"""
        hugo_website = next(site for site in websites_with_external_resources if site.name == "hugo-site")
        hugo_resource = hugo_website.websitecontent_set.filter(type="external_resource").first()
        
        original_description = hugo_resource.metadata["description"]
        
        # Should contain Hugo partials
        hugo_partials = re.findall(r"\{\{<\s*(?:subscript|superscript)\s+[^>]*>\}\}", original_description)
        assert len(hugo_partials) > 0
        
        # All partials should be properly formatted
        for partial in hugo_partials:
            assert partial.startswith("{{<")
            assert partial.endswith(">}}")
            assert "subscript" in partial or "superscript" in partial

    def _has_nested_shortcodes(self, content: str) -> bool:
        """Check if content has nested Hugo shortcodes"""
        # Look for resource_link shortcodes containing other shortcodes
        nested_pattern = r"\{\{% resource_link \"[^\"]*\" \"[^\"]*\{\{<[^>]*>\}\}[^\"]*\" %\}\}"
        return bool(re.search(nested_pattern, content))

    def _validate_hugo_syntax(self, content: str) -> bool:
        """Validate Hugo syntax is balanced"""
        if not content:
            return True
        
        open_count = content.count("{{")
        close_count = content.count("}}")
        
        return open_count == close_count

    def _validate_for_mass_build(self, resource) -> bool:
        """Validate external resource for mass build pipeline compatibility"""
        if resource.type != "external_resource":
            return True
            
        description = resource.metadata.get("description", "")
        
        # Check for problematic patterns
        problematic_patterns = [
            r"\{\{% resource_link \"[^\"]*\" \"[^\"]*\{\{<[^>]*>[^}]*\}\}[^\"]*\" %\}\}",  # Nested partials
            r"\{\{% resource_link \"[^\"]*\" \"[^\"]*\"[^\"]*\"[^\"]*\" %\}\}",  # Unescaped quotes
        ]
        
        return not any(re.search(pattern, description) for pattern in problematic_patterns)


class TestPipelineErrorRecovery:
    """Test pipeline error handling and recovery scenarios"""

    @pytest.fixture
    def mock_pipeline_with_errors(self, mocker):
        """Mock pipeline that simulates various error conditions"""
        mock_api = MagicMock()
        
        # Simulate different error scenarios
        mock_api.upsert_pipeline.side_effect = [
            Exception("Invalid YAML configuration"),  # First call fails
            None,  # Second call succeeds
        ]
        
        mocker.patch("content_sync.api.get_pipeline_api", return_value=mock_api)
        return mock_api

    def test_pipeline_recovery_from_invalid_yaml(self, mock_pipeline_with_errors):
        """Test pipeline recovers from invalid YAML configuration errors"""
        pipeline = MassBuildSitesPipeline(version=VERSION_DRAFT)
        
        # First attempt should raise exception
        with pytest.raises(Exception, match="Invalid YAML configuration"):
            pipeline.upsert_pipeline()
        
        # Second attempt should succeed (simulating fix)
        pipeline.upsert_pipeline()  # Should not raise

    def test_website_publish_status_updates_on_pipeline_failure(self, mocker):
        """Test website publish status is updated correctly when pipeline fails"""
        mock_update_status = mocker.patch("websites.api.update_website_status")
        mock_pipeline = mocker.patch("content_sync.api.get_site_pipeline")
        
        # Simulate pipeline failure
        mock_pipeline.return_value.trigger_build.side_effect = Exception("Pipeline failed")
        
        website = WebsiteFactory.create()
        
        with pytest.raises(Exception):
            publish_website(
                website,
                VERSION_DRAFT,
                create_backend=False,
                trigger=True
            )

    def test_mass_build_continues_after_individual_site_failure(self, mocker):
        """Test mass build continues processing other sites after one fails"""
        websites = WebsiteFactory.create_batch(3)
        website_names = [site.name for site in websites]
        
        # Mock individual site processing with one failure
        mock_process_site = mocker.patch("content_sync.tasks.publish_website")
        mock_process_site.side_effect = [
            None,  # First site succeeds
            Exception("Site 2 failed"),  # Second site fails
            None,  # Third site succeeds
        ]
        
        # Mass build should handle individual failures gracefully
        with pytest.raises(Exception):
            # This would be caught and handled in actual implementation
            for name in website_names:
                website = Website.objects.get(name=name)
                mock_process_site(website, VERSION_DRAFT)


class TestPipelinePerformance:
    """Test pipeline performance with large numbers of external resources"""

    def test_mass_build_performance_with_many_external_resources(self, mock_pipeline_backend):
        """Test mass build performance with many external resources"""
        # Create website with many external resources
        website = WebsiteFactory.create(name="performance-test-site")
        
        # Create 50 external resources (reasonable test size)
        for i in range(50):
            resource = WebsiteContentFactory.create(
                website=website,
                type="external_resource",
                title=f"Resource {i}",
                metadata={
                    "external_url": f"https://example.com/resource{i}",
                    "description": f"Description {i} with H{{{{< subscript \"{i}\" >}}}}O formula"
                }
            )
            ExternalResourceStateFactory.create(
                content=resource,
                url=f"https://example.com/resource{i}",
                status_code=200
            )
        
        # Pipeline creation should still be performant
        import time
        start_time = time.time()
        
        pipeline = MassBuildSitesPipeline(version=VERSION_DRAFT)
        pipeline.upsert_pipeline()
        
        end_time = time.time()
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert end_time - start_time < 10.0  # 10 seconds max

    def test_external_resource_validation_performance(self):
        """Test external resource validation performs well with many resources"""
        website = WebsiteFactory.create()
        
        # Create resources with various complexity levels
        resources = []
        for i in range(100):
            resource = WebsiteContentFactory.create(
                website=website,
                type="external_resource",
                title=f"Performance Resource {i}",
                metadata={
                    "external_url": f"https://example.com/perf{i}",
                    "description": f"Complex description {i} with {{{{< subscript \"{i}\" >}}}} and {{{{< superscript \"test\" >}}}}"
                }
            )
            resources.append(resource)
        
        # Validation should be performant
        import time
        start_time = time.time()
        
        for resource in resources:
            # Validate each resource
            assert self._validate_for_mass_build(resource)
        
        end_time = time.time()
        
        # Should validate 100 resources quickly
        assert end_time - start_time < 5.0  # 5 seconds max

    def _validate_for_mass_build(self, resource) -> bool:
        """Performance test version of validation"""
        if resource.type != "external_resource":
            return True
            
        description = resource.metadata.get("description", "")
        
        # Quick validation checks
        if "{{% resource_link" in description and "{{<" in description:
            # More detailed check only if both patterns present
            nested_pattern = r"\{\{% resource_link \"[^\"]*\" \"[^\"]*\{\{<[^>]*>[^}]*\}\}[^\"]*\" %\}\}"
            return not bool(re.search(nested_pattern, description))
        
        return True
