import json
import os
from urllib.parse import quote, urljoin

import pytest
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    STATIC_RESOURCES_S3_IDENTIFIER,
    WEBPACK_ARTIFACTS_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    BUILD_OFFLINE_SITE_IDENTIFIER,
    BUILD_ONLINE_SITE_IDENTIFIER,
    CLEAR_CDN_CACHE_IDENTIFIER,
    FILTER_WEBPACK_ARTIFACTS_IDENTIFIER,
    UPLOAD_OFFLINE_BUILD_IDENTIFIER,
    UPLOAD_ONLINE_BUILD_IDENTIFIER,
    SitePipelineDefinition,
    SitePipelineDefinitionConfig,
)
from main.utils import get_dict_list_item_by_field
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
from websites.factories import WebsiteFactory, WebsiteStarterFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("site_name", ["test-site", "root-website"])
@pytest.mark.parametrize(
    "branch_vars",
    [
        {
            "pipeline_name": "draft",
            "branch": "preview",
            "pipeline_name": VERSION_DRAFT,  # noqa: F601
            "static_api_url": "https://draft.ocw.mit.edu/",
            "web_bucket": "ocw-content-draft",
            "offline_bucket": "ocw-content-draft-offline",
        },
        {
            "pipeline_name": "live",
            "branch": "release",
            "pipeline_name": VERSION_LIVE,  # noqa: F601
            "static_api_url": "https://ocw.mit.edu/",
            "web_bucket": "ocw-content-live",
            "offline_bucket": "ocw-content-live-offline",
        },
    ],
)
@pytest.mark.parametrize("concourse_is_private_repo", [True, False])
@pytest.mark.parametrize("ocw_hugo_themes_branch", ["main", "test_branch"])
@pytest.mark.parametrize("ocw_hugo_projects_branch", ["main", "test_branch"])
@pytest.mark.parametrize("env_name", ["dev", "prod"])
@pytest.mark.parametrize("hugo_override_args", ["", "--verbose"])
@pytest.mark.parametrize("is_dev", [True, False])
def test_generate_theme_assets_pipeline_definition(  # noqa: C901, PLR0912, PLR0913, PLR0915
    settings,
    mocker,
    site_name,
    branch_vars,
    concourse_is_private_repo,
    ocw_hugo_themes_branch,
    ocw_hugo_projects_branch,
    env_name,
    hugo_override_args,
    is_dev,
):
    """
    The site pipeline definition should contain the expected properties
    """
    settings.AWS_ACCESS_KEY_ID = "test_access_key_id"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"  # noqa: S105
    settings.CONCOURSE_IS_PRIVATE_REPO = concourse_is_private_repo
    settings.OCW_HUGO_THEMES_SENTRY_DSN = "test_sentry_dsn"
    settings.ROOT_WEBSITE_NAME = "root-website"
    settings.ENV_NAME = env_name
    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_is_dev.return_value = is_dev
    cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev else ""
    hugo_projects_path = "https://github.com/org/repo"
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
    )
    site = WebsiteFactory.create(
        starter=starter,
        name=site_name,
    )
    other_vars = {
        "resource_base_url": "http://localhost:8044/"
        if branch_vars["pipeline_name"] == VERSION_DRAFT
        else "http://localhost:8045/",
        "ocw_studio_url": "http://10.1.0.102:8043/"
        if branch_vars["pipeline_name"] == VERSION_DRAFT
        else "https://ocw.mit.edu/",
    }
    branch_vars.update(other_vars)
    storage_bucket = "ol-ocw-studio-app"
    artifacts_bucket = "ol-eng-artifacts"
    instance_vars = f"?vars={quote(json.dumps({'site': site_name}))}"
    config = SitePipelineDefinitionConfig(
        site=site,
        pipeline_name=branch_vars["pipeline_name"],
        instance_vars=instance_vars,
        site_content_branch=branch_vars["branch"],
        static_api_url=branch_vars["static_api_url"],
        storage_bucket=storage_bucket,
        artifacts_bucket=artifacts_bucket,
        web_bucket=branch_vars["web_bucket"],
        offline_bucket=branch_vars["offline_bucket"],
        resource_base_url=branch_vars["resource_base_url"],
        ocw_studio_url=branch_vars["ocw_studio_url"],
        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
        ocw_hugo_projects_branch=ocw_hugo_projects_branch,
        hugo_override_args=hugo_override_args,
    )
    pipeline_definition = SitePipelineDefinition(config=config)
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
    for resource in resources:
        assert resource["check_every"] == "never"
    webpack_manifest_s3_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=WEBPACK_MANIFEST_S3_IDENTIFIER
    )
    assert (
        webpack_manifest_s3_resource["source"]["bucket"]
        == config.vars["artifacts_bucket"]
    )
    assert (
        webpack_manifest_s3_resource["source"]["versioned_file"]
        == f"ocw-hugo-themes/{config.vars['ocw_hugo_themes_branch']}/webpack.json"
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
    offline_build_gate_resource = get_dict_list_item_by_field(
        items=resources,
        field="name",
        value=pipeline_definition._offline_build_gate_identifier,  # noqa: SLF001
    )
    assert offline_build_gate_resource["type"] == "keyval"
    site_content_git_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=SITE_CONTENT_GIT_IDENTIFIER
    )
    assert (
        site_content_git_resource["source"]["branch"]
        == config.vars["site_content_branch"]
    )
    site_content_git_uri = site_content_git_resource["source"]["uri"]
    if concourse_is_private_repo:
        assert (
            site_content_git_uri
            == f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{config.vars['short_id']}.git"
        )
        assert (
            site_content_git_resource["source"]["private_key"] == "((git-private-key))"
        )
    else:
        assert (
            site_content_git_uri
            == f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{config.vars['short_id']}.git"
        )
        assert not hasattr(site_content_git_resource["source"], "private_key")
    ocw_hugo_themes_git_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=OCW_HUGO_THEMES_GIT_IDENTIFIER
    )
    assert ocw_hugo_themes_git_resource["source"]["uri"] == OCW_HUGO_THEMES_GIT
    assert (
        ocw_hugo_themes_git_resource["source"]["branch"]
        == config.vars["ocw_hugo_themes_branch"]
    )
    ocw_hugo_projects_git_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=OCW_HUGO_PROJECTS_GIT_IDENTIFIER
    )
    assert (
        ocw_hugo_projects_git_resource["source"]["uri"]
        == config.vars["ocw_hugo_projects_url"]
    )
    assert (
        ocw_hugo_projects_git_resource["source"]["branch"]
        == config.vars["ocw_hugo_projects_branch"]
    )
    ocw_studio_webhook_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    expected_api_path = os.path.join(  # noqa: PTH118
        "api", "websites", config.vars["site_name"], "pipeline_status"
    )
    expected_api_url = urljoin(branch_vars["ocw_studio_url"], expected_api_path)
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

    # The build jobs should contain the expected tasks, and those tasks should have the expected properties
    def assert_base_build_tasks(tasks: list[dict], offline: bool):  # noqa: FBT001
        """
        Asserts that a list of tasks contains the proper base site pipeline tasks

        Args:
            tasks(list[dict]): The list of tasks to check
        """  # noqa: D401
        get_steps = [
            WEBPACK_MANIFEST_S3_IDENTIFIER,
            OCW_HUGO_THEMES_GIT_IDENTIFIER,
            OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            SITE_CONTENT_GIT_IDENTIFIER,
        ]
        for get_step in get_steps:
            step = get_dict_list_item_by_field(items=tasks, field="get", value=get_step)
            assert step is not None
            if offline:
                assert (
                    pipeline_definition._online_site_job_identifier  # noqa: SLF001
                    in step["passed"]  # noqa: RUF100, SLF001
                )
        static_resources_s3_task = get_dict_list_item_by_field(
            items=tasks, field="task", value=STATIC_RESOURCES_S3_IDENTIFIER
        )
        static_resources_command = "\n".join(
            static_resources_s3_task["config"]["run"]["args"]
        )
        assert (
            get_dict_list_item_by_field(
                items=static_resources_s3_task["config"]["outputs"],
                field="name",
                value=STATIC_RESOURCES_S3_IDENTIFIER,
            )
            is not None
        )
        assert f"aws s3{cli_endpoint_url} sync s3://{storage_bucket}/{site.s3_path} ./{STATIC_RESOURCES_S3_IDENTIFIER}"  # noqa: PLW0129
        if is_dev:
            assert cli_endpoint_url in static_resources_command
            assert set(
                {
                    "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                    "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
                }
            ).issubset(set(static_resources_s3_task["params"]))

    jobs = rendered_definition["jobs"]
    online_site_job = get_dict_list_item_by_field(
        jobs, "name", pipeline_definition._online_site_job_identifier  # noqa: SLF001
    )
    online_site_tasks = online_site_job["plan"]
    assert (
        online_site_tasks[0]["try"]["put"]
        == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    assert_base_build_tasks(tasks=online_site_tasks, offline=False)
    build_online_site_task = get_dict_list_item_by_field(
        items=online_site_tasks, field="task", value=BUILD_ONLINE_SITE_IDENTIFIER
    )
    assert (
        build_online_site_task["config"]["image_resource"]["source"]["repository"]
        == OCW_COURSE_PUBLISHER_REGISTRY_IMAGE.source.repository
    )
    build_online_site_expected_inputs = [
        OCW_HUGO_THEMES_GIT_IDENTIFIER,
        OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
        SITE_CONTENT_GIT_IDENTIFIER,
        STATIC_RESOURCES_S3_IDENTIFIER,
        WEBPACK_MANIFEST_S3_IDENTIFIER,
    ]
    for input in build_online_site_task["config"]["inputs"]:  # noqa: A001
        assert input["name"] in build_online_site_expected_inputs
    build_online_site_expected_outputs = [
        SITE_CONTENT_GIT_IDENTIFIER,
        OCW_HUGO_THEMES_GIT_IDENTIFIER,
    ]
    for output in build_online_site_task["config"]["outputs"]:
        assert output["name"] in build_online_site_expected_outputs
    build_online_site_command = "\n".join(
        build_online_site_task["config"]["run"]["args"]
    )
    assert (
        f"cp ../{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json ../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/data"
        in build_online_site_command
    )
    assert f"hugo {config.vars['hugo_args_online']}" in build_online_site_command
    assert (
        f"cp -r -n ../{STATIC_RESOURCES_S3_IDENTIFIER}/. ./output-online{config.vars['static_resources_subdirectory']}"
        in build_online_site_command
    )
    assert (
        f"rm -rf ./output-online{config.vars['static_resources_subdirectory']}*.mp4"
        in build_online_site_command
    )
    build_online_site_expected_params = {
        "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
        "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
        "OCW_STUDIO_BASE_URL": branch_vars["ocw_studio_url"],
        "STATIC_API_BASE_URL": branch_vars["static_api_url"],
        "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
        "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
        "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
        "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
        "NOINDEX": config.noindex,
    }
    if is_dev:
        build_online_site_expected_params.update(
            {
                "RESOURCE_BASE_URL": branch_vars["resource_base_url"],
                "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            }
        )
    assert set(build_online_site_expected_params).issubset(
        set(build_online_site_task["params"])
    )
    upload_online_build_task = get_dict_list_item_by_field(
        items=online_site_tasks, field="task", value=UPLOAD_ONLINE_BUILD_IDENTIFIER
    )
    assert (
        upload_online_build_task["config"]["image_resource"]["source"]["repository"]
        == AWS_CLI_REGISTRY_IMAGE.source.repository
    )
    upload_online_build_command = "\n".join(
        upload_online_build_task["config"]["run"]["args"]
    )
    assert (
        f"aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{config.vars['web_bucket']}/{config.vars['base_url']} --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        in upload_online_build_command
    )
    assert (
        f"aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{config.vars['web_bucket']}/{config.vars['base_url']} --exclude='{config.vars['short_id']}.zip' --exclude='{config.vars['short_id']}-video.zip' --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        in upload_online_build_command
    )
    upload_online_build_expected_inputs = [SITE_CONTENT_GIT_IDENTIFIER]
    for input in upload_online_build_task["config"]["inputs"]:  # noqa: A001
        assert input["name"] in upload_online_build_expected_inputs
    assert (
        upload_online_build_task["on_success"]["try"]["put"]
        == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    assert (
        upload_online_build_task["on_success"]["try"]["params"]["text"]
        == f"{{\"version\": \"{config.vars['pipeline_name']}\", \"status\": \"succeeded\"}}"
    )
    if is_dev:
        assert set(
            {
                "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            }
        ).issubset(set(upload_online_build_task["params"]))
    if not is_dev:
        clear_cdn_cache_online_step = get_dict_list_item_by_field(
            online_site_tasks, "task", CLEAR_CDN_CACHE_IDENTIFIER
        )
        clear_cdn_cache_online_success_steps = clear_cdn_cache_online_step[
            "on_success"
        ]["try"]["do"]
        open_discussions_webhook_step_online_params = json.loads(
            clear_cdn_cache_online_success_steps[0]["try"]["params"]["text"]
        )
        assert (
            open_discussions_webhook_step_online_params["webhook_key"]
            == settings.OCW_NEXT_SEARCH_WEBHOOK_KEY
        )
        assert (
            open_discussions_webhook_step_online_params["prefix"]
            == f"{config.vars['url_path']}/"
        )
        assert (
            open_discussions_webhook_step_online_params["version"]
            == config.vars["pipeline_name"]
        )
    assert (
        online_site_tasks[-1]["put"]
        == pipeline_definition._offline_build_gate_identifier  # noqa: SLF001
    )
    offline_site_job = get_dict_list_item_by_field(
        jobs, "name", pipeline_definition._offline_site_job_identifier  # noqa: SLF001
    )
    offline_site_tasks = offline_site_job["plan"]
    offline_build_gate_get_task = offline_site_tasks[0]
    assert (
        offline_build_gate_get_task["get"]
        == pipeline_definition._offline_build_gate_identifier  # noqa: SLF001
    )
    assert (
        pipeline_definition._online_site_job_identifier  # noqa: SLF001
        in offline_build_gate_get_task["passed"]
    )
    assert_base_build_tasks(tasks=offline_site_tasks, offline=True)
    filter_webpack_artifacts_task = get_dict_list_item_by_field(
        offline_site_tasks, "task", FILTER_WEBPACK_ARTIFACTS_IDENTIFIER
    )
    assert (
        filter_webpack_artifacts_task["config"]["image_resource"]["source"][
            "repository"
        ]
        == OCW_COURSE_PUBLISHER_REGISTRY_IMAGE.source.repository
    )
    filter_webpack_artifacts_expected_inputs = [WEBPACK_MANIFEST_S3_IDENTIFIER]
    for input in filter_webpack_artifacts_task["config"]["inputs"]:  # noqa: A001
        assert input["name"] in filter_webpack_artifacts_expected_inputs
    filter_webpack_artifacts_expected_outputs = [WEBPACK_ARTIFACTS_IDENTIFIER]
    for input in filter_webpack_artifacts_task["config"]["outputs"]:  # noqa: A001
        assert input["name"] in filter_webpack_artifacts_expected_outputs
    filter_webpack_artifacts_command = "\n".join(
        filter_webpack_artifacts_task["config"]["run"]["args"]
    )
    assert (
        f"jq 'recurse | select(type==\"string\")' ./{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json | tr -d '\"' | xargs -I {{}} aws s3{cli_endpoint_url} cp s3://{config.vars['web_bucket']}{{}} ./{WEBPACK_ARTIFACTS_IDENTIFIER}/{{}} --exclude *.js.map"
        in filter_webpack_artifacts_command
    )
    if is_dev:
        assert set(
            {
                "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            }
        ).issubset(set(filter_webpack_artifacts_task["params"]))
    build_offline_site_task = get_dict_list_item_by_field(
        offline_site_tasks,
        "task",
        BUILD_OFFLINE_SITE_IDENTIFIER,
    )
    assert (
        build_offline_site_task["config"]["image_resource"]["source"]["repository"]
        == OCW_COURSE_PUBLISHER_REGISTRY_IMAGE.source.repository
    )
    build_offline_site_expected_inputs = [
        OCW_HUGO_THEMES_GIT_IDENTIFIER,
        OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
        SITE_CONTENT_GIT_IDENTIFIER,
        STATIC_RESOURCES_S3_IDENTIFIER,
        WEBPACK_MANIFEST_S3_IDENTIFIER,
        WEBPACK_ARTIFACTS_IDENTIFIER,
    ]
    for input in build_offline_site_task["config"]["inputs"]:  # noqa: A001
        assert input["name"] in build_offline_site_expected_inputs
    build_offline_site_expected_outputs = [
        SITE_CONTENT_GIT_IDENTIFIER,
        OCW_HUGO_THEMES_GIT_IDENTIFIER,
        BUILD_OFFLINE_SITE_IDENTIFIER,
    ]
    for input in build_offline_site_task["config"]["outputs"]:  # noqa: A001
        assert input["name"] in build_offline_site_expected_outputs
    build_offline_site_command = "\n".join(
        build_offline_site_task["config"]["run"]["args"]
    )
    assert WEBPACK_MANIFEST_S3_IDENTIFIER in build_offline_site_command
    assert OCW_HUGO_THEMES_GIT_IDENTIFIER in build_offline_site_command
    assert STATIC_RESOURCES_S3_IDENTIFIER in build_offline_site_command
    assert WEBPACK_ARTIFACTS_IDENTIFIER in build_offline_site_command
    assert (
        build_offline_site_command.count(f"hugo {config.vars['hugo_args_offline']}")
        == 2
    )
    assert f"zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{config.vars['short_id']}-video.zip ./"  # noqa: PLW0129
    build_offline_site_expected_params = {
        "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
        "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
        "OCW_STUDIO_BASE_URL": branch_vars["ocw_studio_url"],
        "STATIC_API_BASE_URL": branch_vars["static_api_url"],
        "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
        "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
        "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
        "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
        "NOINDEX": config.noindex,
    }
    if is_dev:
        build_offline_site_expected_params.update(
            {
                "RESOURCE_BASE_URL": branch_vars["resource_base_url"],
                "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            }
        )
    assert set(build_offline_site_expected_params).issubset(
        set(build_offline_site_task["params"])
    )
    upload_offline_build_task = get_dict_list_item_by_field(
        offline_site_tasks, "task", UPLOAD_OFFLINE_BUILD_IDENTIFIER
    )
    assert (
        upload_offline_build_task["config"]["image_resource"]["source"]["repository"]
        == AWS_CLI_REGISTRY_IMAGE.source.repository
    )
    upload_offline_build_command = "\n".join(
        upload_offline_build_task["config"]["run"]["args"]
    )
    assert (
        f"aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{config.vars['offline_bucket']}/{config.vars['base_url']} --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        in upload_offline_build_command
    )
    assert (
        f"aws s3{cli_endpoint_url} sync {BUILD_OFFLINE_SITE_IDENTIFIER}/ s3://{config.vars['web_bucket']}/{config.vars['base_url']} --exclude='*' --include='{config.vars['short_id']}.zip' --include='{config.vars['short_id']}-video.zip' --metadata site-id={config.vars['site_name']}"
        in upload_offline_build_command
    )
    upload_offline_build_expected_inputs = [
        SITE_CONTENT_GIT_IDENTIFIER,
        BUILD_OFFLINE_SITE_IDENTIFIER,
        OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    ]
    for input in upload_offline_build_task["config"]["inputs"]:  # noqa: A001
        assert input["name"] in upload_offline_build_expected_inputs
    if is_dev:
        assert set(
            {
                "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            }
        ).issubset(set(upload_offline_build_task["params"]))
    if not is_dev:
        clear_cdn_cache_offline_step = get_dict_list_item_by_field(
            offline_site_tasks, "task", CLEAR_CDN_CACHE_IDENTIFIER
        )
        clear_cdn_cache_offline_success_steps = clear_cdn_cache_offline_step[
            "on_success"
        ]["try"]["do"]
        open_discussions_webhook_step_offline_params = json.loads(
            clear_cdn_cache_offline_success_steps[0]["try"]["params"]["text"]
        )
        assert (
            open_discussions_webhook_step_offline_params["webhook_key"]
            == settings.OCW_NEXT_SEARCH_WEBHOOK_KEY
        )
        assert (
            open_discussions_webhook_step_offline_params["prefix"]
            == f"{config.vars['url_path']}/"
        )
        assert (
            open_discussions_webhook_step_offline_params["version"]
            == config.vars["pipeline_name"]
        )
    site_dummy_var_source = get_dict_list_item_by_field(
        rendered_definition["var_sources"], "name", "site"
    )
    dummy_vars = site_dummy_var_source["config"]["vars"]
    assert dummy_vars["short_id"] == site.short_id
    assert dummy_vars["site_name"] == site.name
    assert dummy_vars["s3_path"] == site.s3_path
    assert dummy_vars["url_path"] == site.get_url_path()
    assert dummy_vars["base_url"] == config.base_url
    assert (
        dummy_vars["static_resources_subdirectory"]
        == config.static_resources_subdirectory
    )
    assert dummy_vars["delete_flag"] == config.delete_flag
    assert dummy_vars["noindex"] == config.noindex
    assert dummy_vars["pipeline_name"] == branch_vars["pipeline_name"]
    assert dummy_vars["instance_vars"] == instance_vars
    assert dummy_vars["static_api_url"] == branch_vars["static_api_url"]
    assert dummy_vars["storage_bucket"] == storage_bucket
    assert dummy_vars["artifacts_bucket"] == artifacts_bucket
    assert dummy_vars["web_bucket"] == branch_vars["web_bucket"]
    assert dummy_vars["offline_bucket"] == branch_vars["offline_bucket"]
    assert dummy_vars["resource_base_url"] == branch_vars["resource_base_url"]
    assert dummy_vars["ocw_studio_url"] == branch_vars["ocw_studio_url"]
    assert dummy_vars["site_content_branch"] == branch_vars["branch"]
    assert dummy_vars["ocw_hugo_themes_branch"] == ocw_hugo_themes_branch
    assert dummy_vars["ocw_hugo_projects_url"] == site.starter.ocw_hugo_projects_url
    assert dummy_vars["ocw_hugo_projects_branch"] == ocw_hugo_projects_branch
    assert dummy_vars["hugo_args_online"] == config.hugo_args_online
    assert dummy_vars["hugo_args_offline"] == config.hugo_args_offline
