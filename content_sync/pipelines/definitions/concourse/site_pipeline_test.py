import json
import os
from urllib.parse import quote, urljoin, urlparse

import pytest
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import (
    DEV_ENDPOINT_URL,
    TARGET_OFFLINE,
    TARGET_ONLINE,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
    STATIC_RESOURCES_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    SitePipelineDefinition,
)
from content_sync.utils import get_hugo_arg_string
from main.constants import PRODUCTION_NAMES
from main.utils import get_dict_list_item_by_field
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
from websites.factories import WebsiteFactory, WebsiteStarterFactory


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("is_root_website", [True, False])
@pytest.mark.parametrize(
    "branch_vars",
    [
        {
            "pipeline_name": "draft",
            "branch": "preview",
            "pipeline_name": VERSION_DRAFT,
            "static_api_url": "https://draft.ocw.mit.edu/",
            "web_bucket": "ocw-content-draft",
            "offline_bucket": "ocw-content-draft-offline",
        },
        {
            "pipeline_name": "live",
            "branch": "release",
            "pipeline_name": VERSION_LIVE,
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
def test_generate_theme_assets_pipeline_definition(
    settings,
    mocker,
    is_root_website,
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
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"
    settings.CONCOURSE_IS_PRIVATE_REPO = concourse_is_private_repo
    settings.OCW_HUGO_THEMES_SENTRY_DSN = "test_sentry_dsn"
    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_is_dev.return_value = is_dev
    cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev else ""
    hugo_projects_path = "https://github.com/org/repo"
    site_name = "test_site"
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
    )
    site = WebsiteFactory.create(
        starter=starter,
        name=site_name,
    )
    starter_path_url = urlparse(starter.path)
    ocw_hugo_projects_url = urljoin(
        f"{starter_path_url.scheme}://{starter_path_url.netloc}",
        f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git
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
    if is_root_website:
        base_url = ""
        static_resources_subdirectory = f"/{site.get_url_path()}/"
        delete_flag = ""
    else:
        base_url = site.get_url_path()
        static_resources_subdirectory = "/"
        delete_flag = " --delete"
    if branch_vars["branch"] == "preview" or env_name not in PRODUCTION_NAMES:
        noindex = "true"
    else:
        noindex = "false"
    starter_slug = starter.slug
    base_hugo_args = {"--themesDir": f"../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/"}
    base_online_args = base_hugo_args.copy()
    base_online_args.update(
        {
            "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config.yaml",
            "--baseURL": f"/{base_url}",
            "--destination": "output-online",
        }
    )
    base_offline_args = base_hugo_args.copy()
    base_offline_args.update(
        {
            "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config-offline.yaml",
            "--baseURL": "/",
            "--destination": "output-offline",
        }
    )
    hugo_args_online = get_hugo_arg_string(
        TARGET_ONLINE,
        branch_vars["pipeline_name"],
        base_online_args,
        hugo_override_args,
    )
    hugo_args_offline = get_hugo_arg_string(
        TARGET_OFFLINE,
        branch_vars["pipeline_name"],
        base_offline_args,
        hugo_override_args,
    )
    instance_vars = f"?vars={quote(json.dumps({'site': site_name}))}"
    pipeline_definition = SitePipelineDefinition(
        site=site,
        pipeline_name=branch_vars["pipeline_name"],
        is_root_website=is_root_website,
        base_url=base_url,
        site_content_branch=branch_vars["branch"],
        static_api_url=branch_vars["static_api_url"],
        storage_bucket_name=storage_bucket,
        artifacts_bucket=artifacts_bucket,
        web_bucket=branch_vars["web_bucket"],
        offline_bucket=branch_vars["offline_bucket"],
        resource_base_url=branch_vars["resource_base_url"],
        static_resources_subdirectory=static_resources_subdirectory,
        noindex=noindex,
        ocw_studio_url=branch_vars["ocw_studio_url"],
        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
        ocw_hugo_projects_url=ocw_hugo_projects_url,
        ocw_hugo_projects_branch=ocw_hugo_projects_branch,
        hugo_args_online=hugo_args_online,
        hugo_args_offline=hugo_args_offline,
        delete_flag=delete_flag,
        instance_vars=instance_vars,
    )
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
    offline_build_gate_resource = get_dict_list_item_by_field(
        items=resources,
        field="name",
        value=pipeline_definition._offline_build_gate_identifier,
    )
    assert offline_build_gate_resource["type"] == "keyval"
    site_content_git_resource = get_dict_list_item_by_field(
        items=resources, field="name", value=SITE_CONTENT_GIT_IDENTIFIER
    )
    assert site_content_git_resource["source"]["branch"] == branch_vars["branch"]
    site_content_git_uri = site_content_git_resource["source"]["uri"]
    if concourse_is_private_repo:
        assert (
            site_content_git_uri
            == f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{site.short_id}.git"
        )
        assert (
            site_content_git_resource["source"]["private_key"] == "((git-private-key))"
        )
    else:
        assert (
            site_content_git_uri
            == f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{site.short_id}.git"
        )
        assert not hasattr(site_content_git_resource["source"], "private_key")
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
    expected_api_path = os.path.join("api", "websites", site_name, "pipeline_status")
    expected_api_url = urljoin(branch_vars["ocw_studio_url"], expected_api_path)
    assert ocw_studio_webhook_resource["source"]["url"] == expected_api_url
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
    def assert_base_build_tasks(tasks: list[dict], offline: bool):
        """
        Asserts that a list of tasks contains the proper base site pipeline tasks

        Args:
            tasks(list[dict]): The list of tasks to check
        """
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
                assert pipeline_definition._online_site_job_identifier in step["passed"]
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
        assert f"aws s3{cli_endpoint_url} sync s3://{storage_bucket}/{site.s3_path} ./{STATIC_RESOURCES_S3_IDENTIFIER}"
        if is_dev:
            assert cli_endpoint_url in static_resources_command
            assert (
                static_resources_s3_task["params"]["AWS_ACCESS_KEY_ID"]
                == settings.AWS_ACCESS_KEY_ID
            )
            assert (
                static_resources_s3_task["params"]["AWS_SECRET_ACCESS_KEY"]
                == settings.AWS_SECRET_ACCESS_KEY
            )

    jobs = rendered_definition["jobs"]
    online_site_job = get_dict_list_item_by_field(
        jobs, "name", pipeline_definition._online_site_job_identifier
    )
    online_site_tasks = online_site_job["plan"]
    assert (
        online_site_tasks[0]["try"]["put"]
        == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    assert_base_build_tasks(tasks=online_site_tasks, offline=False)
    build_online_site_task = get_dict_list_item_by_field(
        items=online_site_tasks,
        field="task",
        value=pipeline_definition._build_online_site_identifier,
    )
    assert (
        build_online_site_task["config"]["image_resource"]["source"]["repository"]
        == OCW_COURSE_PUBLISHER_REGISTRY_IMAGE.source["repository"]
    )
    build_online_site_expected_inputs = [
        OCW_HUGO_THEMES_GIT_IDENTIFIER,
        OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
        SITE_CONTENT_GIT_IDENTIFIER,
        STATIC_RESOURCES_S3_IDENTIFIER,
        WEBPACK_MANIFEST_S3_IDENTIFIER,
    ]
    for input in build_online_site_task["config"]["inputs"]:
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
    assert f"hugo {hugo_args_online}" in build_online_site_command
    assert (
        f"cp -r -n ../{STATIC_RESOURCES_S3_IDENTIFIER}/. ./output-online{static_resources_subdirectory}"
        in build_online_site_command
    )
    assert (
        f"rm -rf ./output-online{static_resources_subdirectory}*.mp4"
        in build_online_site_command
    )
    assert (
        build_online_site_task["params"]["API_BEARER_TOKEN"]
        == settings.API_BEARER_TOKEN
    )
    assert (
        build_online_site_task["params"]["GTM_ACCOUNT_ID"]
        == settings.OCW_GTM_ACCOUNT_ID
    )
    assert (
        build_online_site_task["params"]["OCW_STUDIO_BASE_URL"]
        == branch_vars["ocw_studio_url"]
    )
    assert (
        build_online_site_task["params"]["OCW_IMPORT_STARTER_SLUG"]
        == settings.OCW_COURSE_STARTER_SLUG
    )
    assert (
        build_online_site_task["params"]["OCW_COURSE_STARTER_SLUG"]
        == settings.OCW_COURSE_STARTER_SLUG
    )
    assert build_online_site_task["params"]["SITEMAP_DOMAIN"] == settings.SITEMAP_DOMAIN
    assert (
        build_online_site_task["params"]["SENTRY_DSN"]
        == settings.OCW_HUGO_THEMES_SENTRY_DSN
    )
    assert build_online_site_task["params"]["NOINDEX"] == noindex
    if is_dev:
        assert (
            build_online_site_task["params"]["RESOURCE_BASE_URL"]
            == branch_vars["resource_base_url"]
        )
        assert (
            build_online_site_task["params"]["AWS_ACCESS_KEY_ID"]
            == settings.AWS_ACCESS_KEY_ID
        )
        assert (
            build_online_site_task["params"]["AWS_SECRET_ACCESS_KEY"]
            == settings.AWS_SECRET_ACCESS_KEY
        )
    upload_online_build_task = get_dict_list_item_by_field(
        items=online_site_tasks,
        field="task",
        value=pipeline_definition._upload_online_build_identifier,
    )
    assert (
        upload_online_build_task["config"]["image_resource"]["source"]["repository"]
        == AWS_CLI_REGISTRY_IMAGE.source["repository"]
    )
    upload_online_build_command = "\n".join(
        upload_online_build_task["config"]["run"]["args"]
    )
    if is_root_website:
        online_sync_command = f"aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{branch_vars['web_bucket']}/{base_url} --metadata site-id={site.name}{delete_flag}"
    else:
        online_sync_command = f"aws s3{cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{branch_vars['web_bucket']}/{base_url} --exclude='{site.short_id}.zip' --exclude='{site.short_id}-video.zip' --metadata site-id={site.name}{delete_flag}"
    assert online_sync_command in upload_online_build_command
    upload_online_build_expected_inputs = [SITE_CONTENT_GIT_IDENTIFIER]
    for input in upload_online_build_task["config"]["inputs"]:
        assert input["name"] in upload_online_build_expected_inputs
    assert (
        upload_online_build_task["on_success"]["try"]["put"]
        == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    assert (
        upload_online_build_task["on_success"]["try"]["params"]["text"]
        == f"{{\"version\": \"{branch_vars['pipeline_name']}\", \"status\": \"succeeded\"}}"
    )
    if is_dev:
        assert (
            upload_online_build_task["params"]["AWS_ACCESS_KEY_ID"]
            == settings.AWS_ACCESS_KEY_ID
        )
        assert (
            upload_online_build_task["params"]["AWS_SECRET_ACCESS_KEY"]
            == settings.AWS_SECRET_ACCESS_KEY
        )
    assert (
        online_site_tasks[-1]["put"]
        == pipeline_definition._offline_build_gate_identifier
    )
    offline_site_job = get_dict_list_item_by_field(
        jobs, "name", pipeline_definition._offline_site_job_identifier
    )
    offline_site_tasks = offline_site_job["plan"]
    offline_build_gate_get_task = offline_site_tasks[0]
    assert (
        offline_build_gate_get_task["get"]
        == pipeline_definition._offline_build_gate_identifier
    )
    assert (
        pipeline_definition._online_site_job_identifier
        in offline_build_gate_get_task["passed"]
    )

    # TODO: remove this debug code
    # f = open(
    #     f"site-pipeline-{branch_vars['branch']}-{'dev' if is_dev else 'prod'}.yml", "w"
    # )
    # f.write(pipeline_definition.json(indent=2, by_alias=True))
    # f.close()
