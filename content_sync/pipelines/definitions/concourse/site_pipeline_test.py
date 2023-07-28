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
    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.site_pipeline.is_dev"
    )
    mock_is_dev.return_value = is_dev
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
    jobs = rendered_definition["jobs"]
    online_site_job = get_dict_list_item_by_field(
        jobs, "name", pipeline_definition._online_site_job_identifier
    )
    # The online build should contain the expected tasks, and those tasks should have the expected properties
    online_build_tasks = online_site_job["plan"]
    assert (
        online_build_tasks[0]["try"]["put"]
        == OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER
    )
    assert online_build_tasks[1]["get"] == WEBPACK_MANIFEST_S3_IDENTIFIER

    # TODO: remove this debug code
    # f = open(
    #     f"site-pipeline-{branch_vars['branch']}-{'dev' if is_dev else 'prod'}.yml", "w"
    # )
    # f.write(pipeline_definition.json(indent=2, by_alias=True))
    # f.close()
