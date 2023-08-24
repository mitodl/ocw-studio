import json
import os
from urllib.parse import quote, urljoin

import pytest
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    MASS_BULID_SITES_PIPELINE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.mass_build_sites import (
    MassBuildSitesPipelineDefinition,
    MassBuildSitesPipelineDefinitionConfig,
)
from main.utils import get_dict_list_item_by_field
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
from websites.factories import WebsiteFactory, WebsiteStarterFactory


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize("ocw_hugo_themes_branch", ["main", "test_branch"])
@pytest.mark.parametrize("ocw_hugo_projects_branch", ["main", "test_branch"])
@pytest.mark.parametrize("env_name", ["dev", "prod"])
@pytest.mark.parametrize("offline", [True, False])
@pytest.mark.parametrize("is_dev", [True, False])
def test_generate_mass_build_sites_definition(
    settings,
    mocker,
    version,
    ocw_hugo_themes_branch,
    ocw_hugo_projects_branch,
    env_name,
    offline,
    is_dev,
):
    """
    The site pipeline definition should contain the expected properties
    """
    settings.AWS_ACCESS_KEY_ID = "test_access_key_id"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"
    settings.OCW_HUGO_THEMES_SENTRY_DSN = "test_sentry_dsn"
    settings.ROOT_WEBSITE_NAME = "root-website"
    settings.OCW_MASS_BUILD_BATCH_SIZE = 4
    settings.OCW_MASS_BUILD_MAX_IN_FLIGHT = 2
    settings.ENV_NAME = env_name
    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_is_dev.return_value = is_dev
    site_content_branch = (
        settings.GIT_BRANCH_PREVIEW
        if version == VERSION_DRAFT
        else settings.GIT_BRANCH_RELEASE
    )
    artifacts_bucket = "ol-eng-artifacts"
    instance_vars = f"?vars={quote(json.dumps({'offline': False, 'prefix': '', 'projects_branch': 'main', 'themes_branch': 'main', 'starter': '', 'version': 'draft'}))}"
    ocw_hugo_projects_path = "https://github.com/org/repo"
    ocw_hugo_projects_url = f"{ocw_hugo_projects_path}.git"
    ocw_studio_url = settings.SITE_BASE_URL
    WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB,
        path=ocw_hugo_projects_path,
        slug=settings.ROOT_WEBSITE_NAME,
    )
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB, path=ocw_hugo_projects_path
    )
    sites = WebsiteFactory.create_batch(8, starter=starter)
    pipeline_config = MassBuildSitesPipelineDefinitionConfig(
        sites=sites,
        version=version,
        ocw_studio_url=ocw_studio_url,
        artifacts_bucket=artifacts_bucket,
        site_content_branch=site_content_branch,
        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
        ocw_hugo_projects_branch=ocw_hugo_projects_branch,
        offline=offline,
        instance_vars=instance_vars,
    )
    pipeline_definition = MassBuildSitesPipelineDefinition(config=pipeline_config)
    rendered_definition = json.loads(pipeline_definition.json(indent=2, by_alias=True))

    # Assert that the expected resource types exist
    expected_resource_types = [
        HTTP_RESOURCE_TYPE_IDENTIFIER,
        KEYVAL_RESOURCE_TYPE_IDENTIFIER,
        S3_IAM_RESOURCE_TYPE_IDENTIFIER,
        slack_notification_resource().name,
    ]
    for resource_type in rendered_definition["resource_types"]:
        assert resource_type["name"] in expected_resource_types

    # Assert that the expected resources exist and have the expected properties
    resources = rendered_definition["resources"]
    webpack_manifest_s3_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=WEBPACK_MANIFEST_S3_IDENTIFIER
    )
    assert webpack_manifest_s3_resource["source"]["bucket"] == artifacts_bucket
    assert (
        webpack_manifest_s3_resource["source"]["versioned_file"]
        == f"ocw-hugo-themes/{ocw_hugo_themes_branch}/webpack.json"
    )
    if is_dev:
        assert webpack_manifest_s3_resource["source"]["endpoint"] == DEV_ENDPOINT_URL
        assert (
            webpack_manifest_s3_resource["source"]["access_key_id"]
            == settings.AWS_ACCESS_KEY_ID
        )
        assert (
            webpack_manifest_s3_resource["source"]["secret_access_key"]
            == settings.AWS_SECRET_ACCESS_KEY
        )
    else:
        assert not hasattr(webpack_manifest_s3_resource["source"], "endpoint")
        assert not hasattr(webpack_manifest_s3_resource["source"], "access_key_id")
        assert not hasattr(webpack_manifest_s3_resource["source"], "secret_access_key")
    ocw_hugo_themes_git_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=OCW_HUGO_THEMES_GIT_IDENTIFIER
    )
    assert ocw_hugo_themes_git_resource["source"]["uri"] == OCW_HUGO_THEMES_GIT
    assert ocw_hugo_themes_git_resource["source"]["branch"] == ocw_hugo_themes_branch
    ocw_hugo_projects_git_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=OCW_HUGO_PROJECTS_GIT_IDENTIFIER
    )
    assert ocw_hugo_projects_git_resource["source"]["uri"] == ocw_hugo_projects_url
    assert (
        ocw_hugo_projects_git_resource["source"]["branch"] == ocw_hugo_projects_branch
    )
    ocw_studio_webhook_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    expected_api_path = os.path.join(
        "api", "websites", MASS_BULID_SITES_PIPELINE_IDENTIFIER, "pipeline_status"
    )
    expected_api_url = urljoin(ocw_studio_url, expected_api_path)
    assert ocw_studio_webhook_resource["source"]["url"] == f"{expected_api_url}/"
    assert (
        ocw_studio_webhook_resource["source"]["headers"]["Authorization"]
        == f"Bearer {settings.API_BEARER_TOKEN}"
    )
    assert (
        get_dict_list_item_by_field(
            items=resources, field="name", value=SLACK_ALERT_RESOURCE_IDENTIFIER
        )
        is not None
    )
