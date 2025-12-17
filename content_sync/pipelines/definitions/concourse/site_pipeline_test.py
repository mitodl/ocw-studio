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
    BASH_REGISTRY_IMAGE,
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
from websites.models import Website, WebsiteStarter

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module", params=["test-site", "root-website"])
def website(request, django_db_setup, django_db_blocker):
    hugo_projects_path = "https://github.com/org/repo"
    with django_db_blocker.unblock():
        # Use unique slug to avoid collisions with other tests
        starter = WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB,
            path=f"{hugo_projects_path}/site",
            slug=f"fixture-starter-{request.param}",
        )
        site = WebsiteFactory.create(
            starter=starter,
            name=request.param,
        )
        yield site
        site.delete()
        starter.delete()


@pytest.fixture
def root_website(settings):
    """Create a root website for tests that need it"""
    settings.ROOT_WEBSITE_NAME = "root-website"

    root_starter, _ = WebsiteStarter.objects.get_or_create(
        slug="test-root-website-starter",
        defaults={
            "source": STARTER_SOURCE_GITHUB,
            "path": "https://github.com/org/repo/root",
            "name": "Root Starter",
            "status": "default",
            "config": {},
        },
    )
    root_site, _ = Website.objects.get_or_create(
        name="root-website",
        defaults={
            "starter": root_starter,
            "url_path": "root",
            "short_id": "root-site",
            "title": "Root Website",
        },
    )
    return root_site


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
@pytest.mark.parametrize(
    "prefix", ["", "test_prefix", "/test_prefix", "/test_prefix/subfolder/"]
)
def test_generate_theme_assets_pipeline_definition(  # noqa: C901, PLR0912, PLR0913, PLR0915
    website,
    settings,
    mocker,
    branch_vars,
    concourse_is_private_repo,
    ocw_hugo_themes_branch,
    ocw_hugo_projects_branch,
    env_name,
    hugo_override_args,
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
    settings.ENV_NAME = env_name
    mock_utils_is_dev = mocker.patch("content_sync.utils.is_dev")
    mock_pipeline_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_utils_is_dev.return_value = is_dev
    mock_pipeline_is_dev.return_value = is_dev
    cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev else ""
    branch_vars.update(
        {
            "resource_base_url": (
                "http://localhost:8044/"
                if branch_vars["pipeline_name"] == VERSION_DRAFT
                else "http://localhost:8045/"
            )
        }
    )
    ocw_studio_url = "http://10.1.0.102:8043" if is_dev else settings.SITE_BASE_URL
    storage_bucket = "ol-ocw-studio-app"
    artifacts_bucket = settings.AWS_ARTIFACTS_BUCKET_NAME
    instance_vars = f"?vars={quote(json.dumps({'site': website.name}))}"
    config = SitePipelineDefinitionConfig(
        site=website,
        pipeline_name=branch_vars["pipeline_name"],
        instance_vars=instance_vars,
        site_content_branch=branch_vars["branch"],
        static_api_url=branch_vars["static_api_url"],
        storage_bucket=storage_bucket,
        artifacts_bucket=artifacts_bucket,
        web_bucket=branch_vars["web_bucket"],
        offline_bucket=branch_vars["offline_bucket"],
        resource_base_url=branch_vars["resource_base_url"],
        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
        ocw_hugo_projects_branch=ocw_hugo_projects_branch,
        hugo_override_args=hugo_override_args,
        prefix=prefix,
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
    assert offline_build_gate_resource["type"] == "http-resource"
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
                    in step["passed"]
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
        assert f"aws s3{cli_endpoint_url} sync s3://{storage_bucket}/{website.s3_path} ./{STATIC_RESOURCES_S3_IDENTIFIER}"  # noqa: PLW0129
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
        jobs,
        "name",
        pipeline_definition._online_site_job_identifier,  # noqa: SLF001
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
    build_online_site_expected_params = {
        "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
        "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
        "OCW_STUDIO_BASE_URL": ocw_studio_url,
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

    base_url = "/".join(
        (
            config.vars["prefix"],
            config.vars["base_url"],
        )
    )
    # root-website: sync each subdirectory (excluding static_shared) with --delete
    assert (
        f'for dir in $(find {SITE_CONTENT_GIT_IDENTIFIER}/output-online -mindepth 1 -maxdepth 1 -type d -not -name "static_shared"); do'
        in upload_online_build_command
    )
    assert (
        f'aws s3{cli_endpoint_url} sync "$dir" "s3://{config.vars["web_bucket"]}/{base_url}$(basename "$dir")" --delete --metadata site-id={config.vars["site_name"]}'
        in upload_online_build_command
    )
    # root-website: copy only root-level files
    assert (
        f'find {SITE_CONTENT_GIT_IDENTIFIER}/output-online -mindepth 1 -maxdepth 1 -type f -exec aws s3{cli_endpoint_url} cp {{}} "s3://{config.vars["web_bucket"]}/{base_url}" --metadata site-id={config.vars["site_name"]} \\;'
        in upload_online_build_command
    )
    # non-root: fallback to a single sync
    assert (
        f'aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online "s3://{config.vars["web_bucket"]}/{base_url}"'
        in upload_online_build_command
    )
    upload_online_build_expected_inputs = [SITE_CONTENT_GIT_IDENTIFIER]
    for input in upload_online_build_task["config"]["inputs"]:  # noqa: A001
        assert input["name"] in upload_online_build_expected_inputs
    assert (
        upload_online_build_task["on_success"]["try"]["put"]
        == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    assert json.loads(
        upload_online_build_task["on_success"]["try"]["params"]["text"]
    ) == {
        "version": f"{config.vars['pipeline_name']}",
        "status": "succeeded",
        "build_id": "$BUILD_ID",
        "build_type": "online",
        "is_cdn_cache_step": False,
    }
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
        clear_cdn_cache_online_failure_steps = clear_cdn_cache_online_step[
            "on_failure"
        ]["try"]["do"]
        open_discussions_webhook_step_online_params = json.loads(
            clear_cdn_cache_online_success_steps[0]["try"]["params"]["text"]
        )
        ocw_webhook_step_online_params = json.loads(
            clear_cdn_cache_online_success_steps[-1]["try"]["params"]["text"]
        )
        ocw_webhook_step_online_cdn_cache_failure_step = json.loads(
            clear_cdn_cache_online_failure_steps[0]["try"]["params"]["text"]
        )
        assert (
            clear_cdn_cache_online_success_steps[-1]["try"]["put"]
            == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
        )
        assert ocw_webhook_step_online_params["build_type"] == "online"
        assert ocw_webhook_step_online_cdn_cache_failure_step["build_type"] == "online"
        if branch_vars["pipeline_name"] == VERSION_DRAFT:
            assert "webhook_key" not in open_discussions_webhook_step_online_params
        elif branch_vars["pipeline_name"] == VERSION_LIVE:
            assert (
                open_discussions_webhook_step_online_params["webhook_key"]
                == settings.OPEN_CATALOG_WEBHOOK_KEY
            )
            assert (
                open_discussions_webhook_step_online_params["prefix"]
                == f"{config.vars['url_path']}/"
            )
            assert (
                open_discussions_webhook_step_online_params["version"]
                == config.vars["pipeline_name"]
            )

    # Verify gate step exists for all websites (including root)
    offline_build_gate_put_task = online_site_tasks[-1]
    assert (
        offline_build_gate_put_task["try"]["put"]
        == pipeline_definition._offline_build_gate_identifier  # noqa: SLF001
    )
    assert offline_build_gate_put_task["try"]["no_get"] is True

    # Test offline job
    offline_site_job = get_dict_list_item_by_field(
        jobs,
        "name",
        pipeline_definition._offline_site_job_identifier,  # noqa: SLF001
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
        f"jq -r 'values[] | split(\"?\")[0]' ./{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json | xargs -I {{}} aws s3{cli_endpoint_url} cp s3://{config.vars['web_bucket']}{{}} ./{WEBPACK_ARTIFACTS_IDENTIFIER}/{{}} --exclude *.js.map"
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
        "if [ $IS_ROOT_WEBSITE = 0 ] ; then\n            cd output-offline"
        in build_offline_site_command
    )
    assert (
        build_offline_site_command.count(f"hugo {config.vars['hugo_args_offline']}")
        == 2
    )
    assert f"zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{config.vars['short_id']}-video.zip ./"  # noqa: PLW0129
    build_offline_site_expected_params = {
        "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
        "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
        "OCW_STUDIO_BASE_URL": ocw_studio_url,
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
        f"if [ $IS_ROOT_WEBSITE = 1 ] ; then\n            aws s3{cli_endpoint_url} cp {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{config.vars['offline_bucket']}/{config.vars['prefix']}{config.vars['base_url']} --recursive --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        in upload_offline_build_command
    )
    assert (
        f"else\n            aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{config.vars['offline_bucket']}/{config.vars['prefix']}{config.vars['base_url']} --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        in upload_offline_build_command
    )
    assert (
        f"if [ $IS_ROOT_WEBSITE = 0 ] ; then\n            aws s3{cli_endpoint_url} sync {BUILD_OFFLINE_SITE_IDENTIFIER}/ s3://{config.vars['web_bucket']}/{config.vars['prefix']}{config.vars['base_url']} --exclude='*' --include='{config.vars['short_id']}.zip' --include='{config.vars['short_id']}-video.zip' --metadata site-id={config.vars['site_name']}"
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
        clear_cdn_cache_offline_failure_steps = clear_cdn_cache_offline_step[
            "on_failure"
        ]["try"]["do"]
        open_discussions_webhook_step_offline_params = json.loads(
            clear_cdn_cache_offline_success_steps[0]["try"]["params"]["text"]
        )
        ocw_webhook_step_offline_params = json.loads(
            clear_cdn_cache_offline_success_steps[-1]["try"]["params"]["text"]
        )
        ocw_webhook_step_offline_cdn_cache_failure_step = json.loads(
            clear_cdn_cache_offline_failure_steps[0]["try"]["params"]["text"]
        )
        assert (
            clear_cdn_cache_offline_success_steps[-1]["try"]["put"]
            == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
        )
        assert ocw_webhook_step_offline_params["build_type"] == "offline"
        assert (
            ocw_webhook_step_offline_cdn_cache_failure_step["build_type"] == "offline"
        )

        if branch_vars["pipeline_name"] == VERSION_DRAFT:
            assert "webhook_key" not in open_discussions_webhook_step_offline_params
        elif branch_vars["pipeline_name"] == VERSION_LIVE:
            assert (
                open_discussions_webhook_step_offline_params["webhook_key"]
                == settings.OPEN_CATALOG_WEBHOOK_KEY
            )
            assert (
                open_discussions_webhook_step_offline_params["prefix"]
                == f"{config.vars['url_path']}/"
            )
            assert (
                open_discussions_webhook_step_offline_params["version"]
                == config.vars["pipeline_name"]
            )

    expected_prefix = prefix.strip("/") if prefix != "" else prefix
    site_dummy_var_source = get_dict_list_item_by_field(
        rendered_definition["var_sources"], "name", "site"
    )
    dummy_vars = site_dummy_var_source["config"]["vars"]
    assert dummy_vars["short_id"] == website.short_id
    assert dummy_vars["site_name"] == website.name
    assert dummy_vars["s3_path"] == website.s3_path
    assert dummy_vars["url_path"] == website.get_url_path()
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
    assert dummy_vars["site_content_branch"] == branch_vars["branch"]
    assert dummy_vars["ocw_hugo_themes_branch"] == ocw_hugo_themes_branch
    assert dummy_vars["ocw_hugo_projects_url"] == website.starter.ocw_hugo_projects_url
    assert dummy_vars["ocw_hugo_projects_branch"] == ocw_hugo_projects_branch
    assert dummy_vars["hugo_args_online"] == config.hugo_args_online
    assert f"--baseURL /{prefix.lstrip('/')}" in dummy_vars["hugo_args_online"]
    assert dummy_vars["hugo_args_offline"] == config.hugo_args_offline
    assert dummy_vars["prefix"] == expected_prefix


@pytest.mark.parametrize("is_dev", [True, False])
def test_offline_content_cleanup_step(website, settings, mocker, is_dev, root_website):
    """
    Test that the offline content cleanup step is correctly configured with all three cleanup tasks
    """
    # Setup
    settings.AWS_ACCESS_KEY_ID = "test_access_key_id"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"  # noqa: S105

    mock_utils_is_dev = mocker.patch("content_sync.utils.is_dev")
    mock_pipeline_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_main_utils_is_dev = mocker.patch("main.utils.is_dev")
    mock_utils_is_dev.return_value = is_dev
    mock_pipeline_is_dev.return_value = is_dev
    mock_main_utils_is_dev.return_value = is_dev
    cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev else ""

    offline_bucket = "test-offline-bucket"
    config = SitePipelineDefinitionConfig(
        site=website,
        pipeline_name="test",
        instance_vars="",
        site_content_branch="main",
        static_api_url="https://test.example.com/",
        storage_bucket="test-storage",
        artifacts_bucket="test-artifacts",
        web_bucket="test-web",
        offline_bucket=offline_bucket,
        resource_base_url="https://test.example.com/",
        ocw_hugo_themes_branch="main",
        ocw_hugo_projects_branch="main",
    )

    pipeline_definition = SitePipelineDefinition(config=config)
    cleanup_step = pipeline_definition.get_offline_content_cleanup_step(config)

    # Test that the cleanup step is a DoStep (not wrapped in TryStep)
    # The outer TryStep wrapping the gate already handles errors
    assert hasattr(cleanup_step, "do")
    assert len(cleanup_step.do) == 2  # S3 cleanup + API call

    # Test Step 1: S3 cleanup task
    s3_cleanup_task = cleanup_step.do[0]
    assert s3_cleanup_task.task == "remove-offline-content-s3-task"
    assert s3_cleanup_task.timeout.root == "5m"
    assert s3_cleanup_task.attempts == 3
    assert s3_cleanup_task.config.run.path == "sh"

    # Check that all three AWS S3 remove commands are present
    actual_command = s3_cleanup_task.config.run.args[1]
    assert (
        f"aws s3{cli_endpoint_url} rm s3://((site:web_bucket))/((site:url_path))/((site:short_id)).zip"
        in actual_command
    )
    assert (
        f"aws s3{cli_endpoint_url} rm s3://((site:web_bucket))/((site:url_path))/((site:short_id))-video.zip"
        in actual_command
    )
    assert (
        f"aws s3{cli_endpoint_url} rm s3://((site:offline_bucket))/((site:url_path))/ --recursive"
        in actual_command
    )
    assert s3_cleanup_task.config.platform == "linux"
    assert s3_cleanup_task.config.image_resource == AWS_CLI_REGISTRY_IMAGE

    # Test environment variables for dev
    if is_dev:
        assert s3_cleanup_task.params["AWS_ACCESS_KEY_ID"] == "test_access_key_id"
        assert (
            s3_cleanup_task.params["AWS_SECRET_ACCESS_KEY"] == "test_secret_access_key"  # noqa: S105
        )
    else:
        assert not hasattr(s3_cleanup_task, "params") or s3_cleanup_task.params is None

    # Test Step 2: API call to remove from root website
    # This triggers root website pipeline rebuild from OCW Studio, not inline
    api_call_task = cleanup_step.do[1]
    assert api_call_task.task == "remove-from-root-website-task"
    assert api_call_task.timeout.root == "10m"
    assert api_call_task.attempts == 3
    assert api_call_task.config.run.path == "sh"

    # Check wget command is used with proper arguments
    api_command = api_call_task.config.run.args[1]
    assert "wget" in api_command
    assert "--post-data=''" in api_command
    assert "/remove_from_root_website/" in api_command
    # Verify version parameter is included so OCW Studio knows which pipeline to trigger
    assert "?version=((site:pipeline_name))" in api_command
    assert api_call_task.config.image_resource == BASH_REGISTRY_IMAGE

    # Verify no on_success handler - root website rebuild is triggered from OCW Studio
    assert not hasattr(api_call_task, "on_success") or api_call_task.on_success is None


@pytest.mark.parametrize("pipeline_name", ["draft", "live"])
def test_offline_build_gate_cleanup_task(
    website, settings, mocker, pipeline_name, root_website
):
    """
    Test that the offline build gate put step has proper failure handling attached
    """
    # Setup
    settings.AWS_ACCESS_KEY_ID = "test_access_key_id"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"  # noqa: S105

    mock_utils_is_dev = mocker.patch("content_sync.utils.is_dev")
    mock_pipeline_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_main_utils_is_dev = mocker.patch("main.utils.is_dev")
    mock_utils_is_dev.return_value = False
    mock_pipeline_is_dev.return_value = False
    mock_main_utils_is_dev.return_value = False

    config = SitePipelineDefinitionConfig(
        site=website,
        pipeline_name=pipeline_name,
        instance_vars="",
        site_content_branch="main",
        static_api_url="https://test.example.com/",
        storage_bucket="test-storage",
        artifacts_bucket="test-artifacts",
        web_bucket="test-web",
        offline_bucket="test-offline-bucket",
        resource_base_url="https://test.example.com/",
        ocw_hugo_themes_branch="main",
        ocw_hugo_projects_branch="main",
    )

    pipeline_definition = SitePipelineDefinition(config=config)
    rendered_definition = json.loads(pipeline_definition.json(indent=2, by_alias=True))

    # Find the online job
    online_job = None
    for job in rendered_definition["jobs"]:
        if job["name"] == "online-site-job":
            online_job = job
            break

    assert online_job is not None, "Online job should exist"

    # Find the offline build gate put step (should be the last step in the online job)
    # This step exists for both root and non-root websites
    gate_put_step = None
    for step in online_job["plan"]:
        if (
            "try" in step
            and "put" in step["try"]
            and step["try"]["put"] == "offline-build-gate"
        ):
            gate_put_step = step["try"]  # Get the inner put step, not the try step
            break

    assert gate_put_step is not None, "Offline build gate put step should exist"

    # Root websites should have the gate step but NO cleanup handler
    if website.name == settings.ROOT_WEBSITE_NAME:
        assert "on_error" not in gate_put_step, (
            "Root websites should not have cleanup (can't remove themselves)"
        )
        return  # Test complete for root websites

    # For non-root websites, verify that failure handling is attached
    assert "on_error" in gate_put_step

    # Verify the failure handling is a DoStep (outer TryStep wrapping gate already handles errors)
    error_handler = gate_put_step["on_error"]
    assert "do" in error_handler, "Error handler should be a DoStep"

    # Verify the cleanup tasks (no need for across since this is a single-site pipeline)
    cleanup_tasks = error_handler["do"]
    assert len(cleanup_tasks) == 2, "Should have S3 cleanup and API call"

    # Verify the S3 cleanup task
    s3_cleanup_task = cleanup_tasks[0]
    assert s3_cleanup_task["task"] == "remove-offline-content-s3-task"
    assert s3_cleanup_task["timeout"] == "5m"
    assert s3_cleanup_task["attempts"] == 3
    assert "rm s3://" in s3_cleanup_task["config"]["run"]["args"][1]
    assert "--recursive" in s3_cleanup_task["config"]["run"]["args"][1]

    # Verify the API call task - triggers root website rebuild from OCW Studio
    remove_content_task = cleanup_tasks[1]
    assert remove_content_task["task"] == "remove-from-root-website-task"
    assert remove_content_task["timeout"] == "10m"
    assert remove_content_task["attempts"] == 3
    assert remove_content_task["config"]["run"]["path"] == "sh"

    # Check wget command is used with proper arguments
    api_args = remove_content_task["config"]["run"]["args"][1]
    assert "wget" in api_args
    assert "--post-data=''" in api_args
    assert "/remove_from_root_website/" in api_args
    # Verify version parameter is included so OCW Studio knows which pipeline to trigger
    assert "?version=" in api_args
    assert "((site:pipeline_name))" in api_args

    # Verify no on_success handler - root website rebuild is triggered from OCW Studio, not inline
    assert "on_success" not in remove_content_task, (
        "Should not have on_success handler - root website rebuild is triggered from OCW Studio"
    )


@pytest.mark.parametrize("noindex", [None, True, False])
@pytest.mark.parametrize("env_name", ["dev", "prod"])
@pytest.mark.parametrize("pipeline_name", [VERSION_DRAFT, VERSION_LIVE])
def test_site_pipeline_definition_config_noindex(
    settings, mocker, noindex, env_name, pipeline_name
):
    settings.ENV_NAME = env_name
    mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev",
        return_value=False,
    )
    hugo_projects_path = "https://github.com/org/repo"
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB,
        path=f"{hugo_projects_path}/site",
        slug="noindex-config-test",
    )
    website = WebsiteFactory.create(starter=starter)

    config = SitePipelineDefinitionConfig(
        site=website,
        pipeline_name=pipeline_name,
        instance_vars="?vars={}",
        site_content_branch="preview" if pipeline_name == VERSION_DRAFT else "release",
        static_api_url="https://ocw.mit.edu/",
        storage_bucket="test-bucket",
        artifacts_bucket="test-artifacts",
        web_bucket="test-web",
        offline_bucket="test-offline",
        resource_base_url="https://ocw.mit.edu/",
        ocw_hugo_themes_branch="main",
        ocw_hugo_projects_branch="main",
        noindex=noindex,
    )

    if noindex is True:
        assert config.noindex == "true"
    elif noindex is False:
        assert config.noindex == "false"
    elif pipeline_name == VERSION_DRAFT or env_name != "prod":
        assert config.noindex == "true"
    else:
        assert config.noindex == "false"


@pytest.mark.parametrize("theme_slug", [None, "ocw-course-v3"])
def test_site_pipeline_definition_config_theme_slug(settings, mocker, theme_slug):
    mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev",
        return_value=False,
    )
    hugo_projects_path = "https://github.com/org/repo"
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB,
        path=f"{hugo_projects_path}/site",
        slug="theme-slug-config-test",
    )
    website = WebsiteFactory.create(starter=starter)

    config = SitePipelineDefinitionConfig(
        site=website,
        pipeline_name=VERSION_LIVE,
        instance_vars="?vars={}",
        site_content_branch="release",
        static_api_url="https://ocw.mit.edu/",
        storage_bucket="test-bucket",
        artifacts_bucket="test-artifacts",
        web_bucket="test-web",
        offline_bucket="test-offline",
        resource_base_url="https://ocw.mit.edu/",
        ocw_hugo_themes_branch="main",
        ocw_hugo_projects_branch="main",
        theme_slug=theme_slug,
    )

    expected_slug = theme_slug if theme_slug else starter.slug
    assert f"/{expected_slug}/config.yaml" in config.hugo_args_online
    assert f"/{expected_slug}/config-offline.yaml" in config.hugo_args_offline
