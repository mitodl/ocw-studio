import json
from urllib.parse import urlparse

import pytest

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.e2e_test_site_pipeline import (
    EndToEndTestPipelineDefinition,
    course_content_git_identifier,
    fetch_built_content_step_identifier,
    playwright_task_identifier,
    test_pipeline_job_identifier,
    upload_fixtures_step_identifier,
    www_content_git_identifier,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    CLEAR_CDN_CACHE_IDENTIFIER,
)
from content_sync.utils import get_cli_endpoint_url, get_common_pipeline_vars
from websites.constants import STARTER_SOURCE_GITHUB
from websites.factories import WebsiteFactory, WebsiteStarterFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def test_sites(request, django_db_setup, django_db_blocker):
    hugo_projects_path = "https://github.com/org/repo"
    with django_db_blocker.unblock():
        starter = WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
        )
        www_site = WebsiteFactory.create(
            starter=starter,
            name="ocw-ci-test-www",
        )
        course_site = WebsiteFactory.create(
            starter=starter,
            name="ocw-ci-test-course",
        )
        yield {"www": www_site, "course": course_site}
        www_site.delete()
        course_site.delete()
        starter.delete()


@pytest.mark.parametrize("ocw_hugo_themes_branch", ["main", "test_branch"])
@pytest.mark.parametrize("ocw_hugo_projects_branch", ["main", "test_branch"])
def test_generate_e2e_test_site_pipeline_definition(  # noqa: PLR0913 PLR0915
    test_sites,
    mock_environments,
    settings,
    mocker,
    ocw_hugo_themes_branch,
    ocw_hugo_projects_branch,
):
    """
    The end to end test pipeline definition should contain the expected properties
    """
    www_site = test_sites["www"]
    course_site = test_sites["course"]
    open_webhook_key = "abc123"
    open_catalog_urls = [
        "https://example.com/api/v0/ocw_next_webhook/",
        "http://other_example.com/api/v1/ocw_next_webhook/",
    ]
    settings.OPEN_CATALOG_URLS = open_catalog_urls
    settings.OPEN_CATALOG_WEBHOOK_KEY = open_webhook_key
    settings.AWS_ACCESS_KEY_ID = "test_access_key_id"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret_access_key"  # noqa: S105
    settings.OCW_HUGO_THEMES_SENTRY_DSN = "test_sentry_dsn"
    mock_utils_is_dev = mocker.patch("content_sync.utils.is_dev")
    mock_pipeline_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.e2e_test_site_pipeline.is_dev"
    )
    is_dev = settings.ENV_NAME == "dev"
    mock_utils_is_dev.return_value = is_dev
    mock_pipeline_is_dev.return_value = is_dev
    common_pipeline_vars = get_common_pipeline_vars()
    static_api_base_url = common_pipeline_vars["static_api_base_url_test"]
    test_bucket = common_pipeline_vars["test_bucket_name"]
    offline_test_bucket = common_pipeline_vars["offline_test_bucket_name"]
    sitemap_domain = urlparse(static_api_base_url).netloc

    pipeline_definition = EndToEndTestPipelineDefinition(
        themes_branch=ocw_hugo_themes_branch,
        projects_branch=ocw_hugo_projects_branch,
    )
    rendered_definition = json.loads(pipeline_definition.json(indent=2))

    jobs = [
        job
        for job in rendered_definition["jobs"]
        if job["name"] == test_pipeline_job_identifier
    ]
    assert len(jobs) == 1
    e2e_test_tasks = jobs[0]["plan"]
    webpack_manifest_get_steps = [
        step
        for step in e2e_test_tasks
        if step.get("get") == WEBPACK_MANIFEST_S3_IDENTIFIER
    ]
    assert len(webpack_manifest_get_steps) == 1
    assert webpack_manifest_get_steps[0]["trigger"] is True
    ocw_hugo_themes_get_steps = [
        step
        for step in e2e_test_tasks
        if step.get("get") == OCW_HUGO_THEMES_GIT_IDENTIFIER
    ]
    assert len(ocw_hugo_themes_get_steps) == 1
    assert ocw_hugo_themes_get_steps[0]["trigger"] is True
    ocw_hugo_projects_get_steps = [
        step
        for step in e2e_test_tasks
        if step.get("get") == OCW_HUGO_PROJECTS_GIT_IDENTIFIER
    ]
    assert len(ocw_hugo_projects_get_steps) == 1
    assert ocw_hugo_projects_get_steps[0]["trigger"] is True
    upload_fixtures_task_steps = [
        step
        for step in e2e_test_tasks
        if step.get("task") == upload_fixtures_step_identifier
    ]
    assert len(upload_fixtures_task_steps) == 1
    upload_fixtures_task_step = upload_fixtures_task_steps[0]
    upload_fixtures_commands = upload_fixtures_task_step["config"]["run"]["args"][
        1
    ].split("\n")
    assert (
        f"aws s3{get_cli_endpoint_url()} sync {OCW_HUGO_THEMES_GIT_IDENTIFIER}/test-sites/__fixtures__/ s3://{common_pipeline_vars['test_bucket_name']}/"
        in upload_fixtures_commands
    )
    assert (
        f"aws s3{get_cli_endpoint_url()} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/test-sites/__fixtures__/api/websites.json s3://{common_pipeline_vars['test_bucket_name']}/api/websites/index.html"
        in upload_fixtures_commands
    )
    assert (
        f"aws s3{get_cli_endpoint_url()} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/test-sites/__fixtures__/api/publish.json s3://{common_pipeline_vars['test_bucket_name']}/api/publish/index.html"
        in upload_fixtures_commands
    )
    if is_dev:
        assert (
            upload_fixtures_task_step["params"]["AWS_ACCESS_KEY_ID"]
            == settings.AWS_ACCESS_KEY_ID
        )
        assert (
            upload_fixtures_task_step["params"]["AWS_SECRET_ACCESS_KEY"]
            == settings.AWS_SECRET_ACCESS_KEY
        )
    else:
        assert not hasattr(upload_fixtures_task_step["params"], "AWS_ACCESS_KEY_ID")
        assert not hasattr(upload_fixtures_task_step["params"], "AWS_SECRET_ACCESS_KEY")
    across_steps = [step for step in e2e_test_tasks if "across" in step]
    assert len(across_steps) == 1
    across_step = across_steps[0]["across"][0]
    assert across_step["max_in_flight"] == 1
    across_values = across_step["values"]
    www_values = next(
        values for values in across_values if values.get("site_name") == www_site.name
    )
    assert www_values["is_root_website"] == 1
    assert www_values["delete_flag"] == ""
    assert www_values["url_path"] == ""
    assert www_values["base_url"] == ""
    assert www_values["ocw_studio_url"] == static_api_base_url
    assert www_values["static_api_url"] == static_api_base_url
    assert www_values["web_bucket"] == test_bucket
    assert www_values["offline_bucket"] == offline_test_bucket
    assert www_values["resource_base_url"] == static_api_base_url
    assert www_values["ocw_hugo_themes_branch"] == ocw_hugo_themes_branch
    assert www_values["ocw_hugo_projects_branch"] == ocw_hugo_projects_branch
    assert www_values["sitemap_domain"] == sitemap_domain
    course_values = next(
        values
        for values in across_values
        if values.get("site_name") == course_site.name
    )
    assert course_values["ocw_studio_url"] == ""
    assert course_values["static_api_url"] == static_api_base_url
    assert course_values["web_bucket"] == test_bucket
    assert course_values["offline_bucket"] == offline_test_bucket
    assert course_values["resource_base_url"] == static_api_base_url
    assert course_values["ocw_hugo_themes_branch"] == ocw_hugo_themes_branch
    assert course_values["ocw_hugo_projects_branch"] == ocw_hugo_projects_branch
    assert course_values["sitemap_domain"] == sitemap_domain
    across_step_build_steps = across_steps[0]["do"]
    cdn_cache_clear_steps = [
        step
        for step in across_step_build_steps
        if step.get("task") == CLEAR_CDN_CACHE_IDENTIFIER
    ]
    assert len(cdn_cache_clear_steps) == 0
    fetch_built_content_steps = [
        step
        for step in e2e_test_tasks
        if step.get("task") == fetch_built_content_step_identifier
    ]
    assert len(fetch_built_content_steps) == 1
    fetch_built_content_step = fetch_built_content_steps[0]
    fetch_built_content_step_commmands = fetch_built_content_step["config"]["run"][
        "args"
    ][1]
    assert (
        "mkdir -p test-sites/tmp/dist/ocw-ci-test-www"
        in fetch_built_content_step_commmands
    )
    assert "mkdir -p test-sites/tmp/dist/courses/" in fetch_built_content_step_commmands
    assert (
        f"aws s3{get_cli_endpoint_url()} sync s3://{test_bucket}/ test-sites/tmp/dist/ocw-ci-test-www/ --exclude *courses/*"
        in fetch_built_content_step_commmands
    )
    assert (
        f"aws s3{get_cli_endpoint_url()} sync s3://{test_bucket}/courses test-sites/tmp/dist/courses/"
        in fetch_built_content_step_commmands
    )
    if is_dev:
        assert (
            fetch_built_content_step["params"]["AWS_ACCESS_KEY_ID"]
            == settings.AWS_ACCESS_KEY_ID
        )
        assert (
            fetch_built_content_step["params"]["AWS_SECRET_ACCESS_KEY"]
            == settings.AWS_SECRET_ACCESS_KEY
        )
    playwright_task_steps = [
        step
        for step in e2e_test_tasks
        if step.get("task") == playwright_task_identifier
    ]
    assert len(playwright_task_steps) == 1
    playwright_task_step = playwright_task_steps[0]
    playwright_task_params = playwright_task_step["config"]["params"]
    assert playwright_task_params["PLAYWRIGHT_BASE_URL"] == static_api_base_url
    assert playwright_task_params["OCW_STUDIO_BASE_URL"] == static_api_base_url
    assert playwright_task_params["STATIC_API_BASE_URL"] == static_api_base_url
    assert playwright_task_params["COURSE_CONTENT_PATH"] == "../"
    assert playwright_task_params["OCW_TEST_COURSE"] == course_content_git_identifier
    assert playwright_task_params["RESOURCE_BASE_URL"] == static_api_base_url
    assert (
        playwright_task_params["SITEMAP_DOMAIN"] == urlparse(static_api_base_url).netloc
    )
    assert playwright_task_params["WEBPACK_WATCH_MODE"] == "false"
    assert playwright_task_params["SENTRY_ENV"] == ""
    assert (
        playwright_task_params["WWW_CONTENT_PATH"] == f"../{www_content_git_identifier}"
    )
