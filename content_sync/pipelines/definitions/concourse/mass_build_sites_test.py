import json
import os
from urllib.parse import quote, urljoin

import pytest
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER,
    MASS_BUILD_SITES_JOB_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    STATIC_RESOURCES_S3_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.mass_build_sites import (
    MassBuildSitesPipelineDefinition,
    MassBuildSitesPipelineDefinitionConfig,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    FILTER_WEBPACK_ARTIFACTS_IDENTIFIER,
    UPLOAD_ONLINE_BUILD_IDENTIFIER,
    SitePipelineDefinitionConfig,
    get_site_pipeline_definition_vars,
)
from content_sync.utils import get_ocw_studio_api_url, get_site_content_branch
from main.utils import get_dict_list_item_by_field
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
from websites.factories import WebsiteFactory, WebsiteStarterFactory

pytestmark = pytest.mark.django_db
total_sites = 6
ocw_hugo_projects_path = "https://github.com/org/repo"


@pytest.fixture(scope="module")
def websites(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        root_starter = WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB,
            path=ocw_hugo_projects_path,
            slug="root-website-starter",
        )
        starter = WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path=ocw_hugo_projects_path
        )
        root_website = WebsiteFactory.create(name="root-website", starter=root_starter)
        batch_sites = WebsiteFactory.create_batch(total_sites, starter=starter)
        batch_sites.append(root_website)
        yield batch_sites
        for site in batch_sites:
            site.delete()
        starter.delete()
        root_starter.delete()


@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize("ocw_hugo_themes_branch", ["main", "test_branch"])
@pytest.mark.parametrize("ocw_hugo_projects_branch", ["main", "test_branch"])
@pytest.mark.parametrize("env_name", ["dev", "prod"])
@pytest.mark.parametrize("concourse_is_private_repo", [True, False])
@pytest.mark.parametrize("offline", [True, False])
@pytest.mark.parametrize("is_dev", [True, False])
@pytest.mark.parametrize(
    "prefix", ["", "test_prefix", "/test_prefix", "/test_prefix/subfolder/"]
)
def test_generate_mass_build_sites_definition(  # noqa: C901, PLR0913, PLR0912 PLR0915
    websites,
    settings,
    mocker,
    version,
    ocw_hugo_themes_branch,
    ocw_hugo_projects_branch,
    env_name,
    concourse_is_private_repo,
    offline,
    is_dev,
    prefix,
):
    """
    The site pipeline definition should contain the expected properties
    """
    settings.AWS_ACCESS_KEY_ID = "test_access_key_id"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"  # noqa: S105
    settings.CONCOURSE_IS_PRIVATE_REPO = concourse_is_private_repo
    settings.OCW_HUGO_THEMES_SENTRY_DSN = "test_sentry_dsn"
    settings.ROOT_WEBSITE_NAME = "root-website"
    settings.OCW_MASS_BUILD_BATCH_SIZE = 2
    settings.OCW_MASS_BUILD_MAX_IN_FLIGHT = 2
    settings.ENV_NAME = env_name
    batch_count = total_sites / settings.OCW_MASS_BUILD_BATCH_SIZE
    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_is_dev.return_value = is_dev
    site_content_branch = get_site_content_branch(version)
    artifacts_bucket = "ol-eng-artifacts"
    web_bucket = (
        settings.AWS_PREVIEW_BUCKET_NAME
        if version == VERSION_DRAFT
        else settings.AWS_PUBLISH_BUCKET_NAME
    )
    offline_bucket = (
        settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME
        if version == VERSION_DRAFT
        else settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME
    )
    instance_vars = f"?vars={quote(json.dumps({'offline': False, 'prefix': '', 'projects_branch': 'main', 'themes_branch': 'main', 'starter': '', 'version': 'draft'}))}"
    ocw_hugo_projects_url = f"{ocw_hugo_projects_path}.git"
    ocw_studio_url = get_ocw_studio_api_url()
    site_pipeline_vars = get_site_pipeline_definition_vars(namespace=".:site.")
    pipeline_config = MassBuildSitesPipelineDefinitionConfig(
        version=version,
        artifacts_bucket=artifacts_bucket,
        site_content_branch=site_content_branch,
        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
        ocw_hugo_projects_branch=ocw_hugo_projects_branch,
        offline=offline,
        instance_vars=instance_vars,
        prefix=prefix,
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
    expected_api_path = os.path.join(  # noqa: PTH118
        "api", "websites", site_pipeline_vars["site_name"], "pipeline_status"
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
    expected_batch_gates_amount = (
        int(total_sites / settings.OCW_MASS_BUILD_BATCH_SIZE) - 1
    )
    for batch_number in range(expected_batch_gates_amount):
        batch_gate = get_dict_list_item_by_field(
            items=resources,
            field="name",
            value=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number + 1}",
        )
        assert batch_gate["type"] == KEYVAL_RESOURCE_TYPE_IDENTIFIER

    # Assert that expected steps exist
    jobs = rendered_definition["jobs"]
    batch_number = 1
    for job in jobs:
        assert job["name"] == f"{MASS_BUILD_SITES_JOB_IDENTIFIER}-batch-{batch_number}"
        steps = job["plan"]
        assert (
            get_dict_list_item_by_field(
                items=steps, field="get", value=WEBPACK_MANIFEST_S3_IDENTIFIER
            )
            is not None
        )
        assert (
            get_dict_list_item_by_field(
                items=steps, field="get", value=OCW_HUGO_THEMES_GIT_IDENTIFIER
            )
            is not None
        )
        assert (
            get_dict_list_item_by_field(
                items=steps, field="get", value=OCW_HUGO_PROJECTS_GIT_IDENTIFIER
            )
            is not None
        )
        if offline:
            assert (
                get_dict_list_item_by_field(
                    items=steps, field="task", value=FILTER_WEBPACK_ARTIFACTS_IDENTIFIER
                )
                is not None
            )
        if batch_number > 1:
            assert (
                get_dict_list_item_by_field(
                    items=steps,
                    field="get",
                    value=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number - 1}",
                )
                is not None
            )
        expected_prefix = f"{prefix.strip('/')}/" if prefix != "" else prefix
        for step in steps:
            if hasattr(step, "across"):
                across_vars = step["across"][0]
                assert across_vars["var"] == "site"
                for across_values in across_vars["values"]:
                    site = websites.get(short_id=across_values["short_id"])
                    site_config = SitePipelineDefinitionConfig(
                        site=site,
                        pipeline_name="test",
                        instance_vars="test",
                        site_content_branch="test",
                        static_api_url="test",
                        storage_bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        artifacts_bucket=artifacts_bucket,
                        web_bucket=web_bucket,
                        offline_bucket=offline_bucket,
                        resource_base_url="",
                        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
                        ocw_hugo_projects_branch=ocw_hugo_projects_branch,
                        hugo_override_args="",
                    )
                    assert across_values["site_name"] == site.name
                    assert across_values["s3_path"] == site.s3_path
                    assert across_values["url_path"] == site.get_url_path()
                    assert across_values["base_url"] == site.get_url_path()
                    assert (
                        across_values["static_resources_subdirectory"]
                        == site_config.static_resources_subdirectory
                    )
                    assert across_values["delete_flag"] == site_config.delete_flag
                    assert across_values["noindex"] == site_config.noindex
                    assert across_values["pipeline_name"] == version
                    assert (
                        across_values["storage_bucket"]
                        == settings.AWS_STORAGE_BUCKET_NAME
                    )
                    assert across_values["artifacts_bucket"] == artifacts_bucket
                    assert across_values["web_bucket"] == web_bucket
                    assert across_values["offline_bucket"] == offline_bucket
                    assert across_values["site_content_branch"] == site_content_branch
                    assert (
                        across_values["ocw_hugo_themes_branch"]
                        == ocw_hugo_themes_branch
                    )
                    assert (
                        across_values["ocw_hugo_projects_url"] == ocw_hugo_projects_url
                    )
                    assert (
                        across_values["ocw_hugo_projects_branch"]
                        == ocw_hugo_projects_branch
                    )
                    assert (
                        across_values["hugo_args_online"]
                        == site_config.hugo_args_online
                    )
                    assert (
                        across_values["hugo_args_offline"]
                        == site_config.hugo_args_offline
                    )
                    assert across_values["prefix"] == expected_prefix
                build_steps = step["do"]
                site_content_git_step = get_dict_list_item_by_field(
                    items=build_steps,
                    field="task",
                    value=SITE_CONTENT_GIT_IDENTIFIER,
                )
                site_content_git_command = site_content_git_step["config"]["run"][
                    "args"
                ][1]
                if concourse_is_private_repo:
                    assert (
                        f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{site_config.vars['short_id']}.git"
                        in site_content_git_command
                    )
                static_resources_s3_step = get_dict_list_item_by_field(
                    items=build_steps,
                    field="task",
                    value=STATIC_RESOURCES_S3_IDENTIFIER,
                )
                static_resources_s3_command = static_resources_s3_step["config"]["run"][
                    "args"
                ].join("\n")
                if offline:
                    assert "--exclude *.mp4" not in static_resources_s3_command
                else:
                    assert "--exclude *.mp4" in static_resources_s3_command
                upload_online_build_task = get_dict_list_item_by_field(
                    items=build_steps,
                    field="task",
                    value=UPLOAD_ONLINE_BUILD_IDENTIFIER,
                )
                upload_online_build_command = upload_online_build_task["config"]["run"][
                    "args"
                ].join("\n")
                assert "--delete" not in upload_online_build_command
        if batch_number < batch_count:
            assert (
                get_dict_list_item_by_field(
                    items=steps,
                    field="put",
                    value=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number}",
                )
                is not None
            )
        batch_number += 1
