import json
from urllib.parse import quote, urlparse

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    AcrossVar,
    Command,
    DoStep,
    Duration,
    GetStep,
    Identifier,
    Input,
    Job,
    Output,
    Pipeline,
    StepModifierMixin,
    TaskConfig,
    TaskStep,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    PLAYWRIGHT_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.common.resource_types import (
    HttpResourceType,
    S3IamResourceType,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    OcwHugoProjectsGitResource,
    OcwHugoThemesGitResource,
    OcwStudioWebhookResource,
    SlackAlertResource,
    WebpackManifestResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    SiteContentGitTaskStep,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    SitePipelineDefinitionConfig,
    SitePipelineOnlineTasks,
    get_site_pipeline_definition_vars,
)
from content_sync.utils import (
    get_cli_endpoint_url,
    get_common_pipeline_vars,
    get_site_content_branch,
)
from main.utils import is_dev
from websites.models import Website

CLI_ENDPOINT_URL = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""

www_content_git_identifier = Identifier("www-content-git").root
course_content_git_identifier = Identifier("course-content-git").root
upload_fixtures_step_identifier = Identifier("upload-fixtures-step").root
fetch_built_content_step_identifier = Identifier("fetch-built-content").root
playwright_task_identifier = Identifier("playwright-task").root
test_pipeline_job_identifier = Identifier("e2e-test-job").root


class TestPipelineBaseTasks(list[StepModifierMixin]):
    """
    The common task objects used in the test pipeline
    """

    def __init__(self):
        common_pipeline_vars = get_common_pipeline_vars()
        webpack_manifest_get_step = GetStep(
            get=WEBPACK_MANIFEST_S3_IDENTIFIER,
            trigger=True,
            timeout="5m",
            attempts=3,
        )
        ocw_hugo_themes_get_step = GetStep(
            get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            trigger=True,
            timeout="5m",
            attempts=3,
        )
        ocw_hugo_projects_get_step = GetStep(
            get=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            trigger=True,
            timeout="5m",
            attempts=3,
        )
        upload_fixtures_step = TaskStep(
            task=upload_fixtures_step_identifier,
            timeout="40m",
            params={
                "AWS_MAX_CONCURRENT_CONNECTIONS": str(
                    settings.AWS_MAX_CONCURRENT_CONNECTIONS
                ),
            },
            config=TaskConfig(
                platform="linux",
                image_resource=AWS_CLI_REGISTRY_IMAGE,
                inputs=[Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER)],
                run=Command(
                    path="sh",
                    args=[
                        "-exc",
                        "\n".join(
                            [
                                "|-",
                                f"aws s3{get_cli_endpoint_url()} sync {OCW_HUGO_THEMES_GIT_IDENTIFIER}/test-sites/__fixtures__/ s3://{common_pipeline_vars['test_bucket_name']}/",  # noqa: E501
                                f"aws s3{get_cli_endpoint_url()} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/test-sites/__fixtures__/api/websites.json s3://{common_pipeline_vars['test_bucket_name']}/api/websites/index.html",  # noqa: E501
                                f"aws s3{get_cli_endpoint_url()} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/test-sites/__fixtures__/api/publish.json s3://{common_pipeline_vars['test_bucket_name']}/api/publish/index.html",  # noqa: E501
                            ]
                        ),
                    ],
                ),
            ),
        )
        if is_dev():
            upload_fixtures_step.params.update(
                {
                    "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                    "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
                }
            )

        self.extend(
            [
                webpack_manifest_get_step,
                ocw_hugo_themes_get_step,
                ocw_hugo_projects_get_step,
                upload_fixtures_step,
            ]
        )


class EndToEndTestPipelineDefinition(Pipeline):
    """
    A Pipeline that does the following:

     - Fetches the ocw-hugo-themes and ocw-hugo-projects repos
     - Runs the steps in SitePipelineOnlineTasks based on test site slugs
     - Deploys the sites to the bucket denoted by AWS_TEST_BUCKET_NAME
     - Runs the Playwright tests from ocw-hugo-themes against the output

    Args:
        themes_branch(str): The branch of ocw-hugo-themes to use
        projects_branch(str): The branch of ocw-hugo-projects to use
    """

    def __init__(self, themes_branch: str, projects_branch: str, **kwargs):
        base = super()
        base.__init__(**kwargs)
        common_pipeline_vars = get_common_pipeline_vars()
        namespace = ".:site."
        site_pipeline_vars = get_site_pipeline_definition_vars(namespace=namespace)
        static_api_base_url = common_pipeline_vars["static_api_base_url_test"]
        site_pipeline_vars["sitemap_domain"] = urlparse(static_api_base_url).netloc
        version = VERSION_LIVE

        www_site = Website.objects.get(name=settings.OCW_WWW_TEST_SLUG)
        course_site = Website.objects.get(name=settings.OCW_COURSE_TEST_SLUG)
        ocw_hugo_projects_url = www_site.starter.ocw_hugo_projects_url
        site_content_branch = get_site_content_branch(version)

        resource_types = [
            HttpResourceType(),
            S3IamResourceType(),
            slack_notification_resource(),
        ]

        webpack_manifest_resource = WebpackManifestResource(
            name=WEBPACK_MANIFEST_S3_IDENTIFIER,
            bucket=common_pipeline_vars["artifacts_bucket_name"],
            branch=themes_branch,
        )
        ocw_hugo_themes_resource = OcwHugoThemesGitResource(branch=themes_branch)
        ocw_hugo_themes_resource.check_every = Duration(root="1m")
        ocw_hugo_projects_resource = OcwHugoProjectsGitResource(
            uri=ocw_hugo_projects_url,
            branch=projects_branch,
        )
        ocw_hugo_projects_resource.check_every = Duration(root="1m")
        ocw_studio_webhook_resource = OcwStudioWebhookResource(
            site_name=course_site.name,
            api_token=settings.API_BEARER_TOKEN or "",
        )

        resources = [
            webpack_manifest_resource,
            ocw_hugo_themes_resource,
            ocw_hugo_projects_resource,
            ocw_studio_webhook_resource,
            SlackAlertResource(),
        ]

        www_config = SitePipelineDefinitionConfig(
            site=www_site,
            pipeline_name=version,
            instance_vars=f"?vars={quote(json.dumps({'site': www_site.name}))}",
            site_content_branch=site_content_branch,
            static_api_url=common_pipeline_vars["static_api_base_url_test"],
            storage_bucket=common_pipeline_vars["storage_bucket_name"],
            artifacts_bucket=common_pipeline_vars["artifacts_bucket_name"],
            web_bucket=common_pipeline_vars["test_bucket_name"],
            offline_bucket=common_pipeline_vars["offline_test_bucket_name"],
            resource_base_url=static_api_base_url,
            ocw_hugo_themes_branch=themes_branch,
            ocw_hugo_projects_branch=projects_branch,
            sitemap_domain=site_pipeline_vars["sitemap_domain"],
            namespace=namespace,
        )
        www_config.is_root_website = True
        www_config.values["is_root_website"] = 1
        www_config.values["delete_flag"] = ""
        www_config.values["url_path"] = ""
        www_config.values["base_url"] = ""
        www_config.values["ocw_studio_url"] = static_api_base_url
        course_config = SitePipelineDefinitionConfig(
            site=course_site,
            pipeline_name=version,
            instance_vars=f"?vars={quote(json.dumps({'site': course_site.name}))}",
            site_content_branch=site_content_branch,
            static_api_url=common_pipeline_vars["static_api_base_url_test"],
            storage_bucket=common_pipeline_vars["storage_bucket_name"],
            artifacts_bucket=common_pipeline_vars["artifacts_bucket_name"],
            web_bucket=common_pipeline_vars["test_bucket_name"],
            offline_bucket=common_pipeline_vars["offline_test_bucket_name"],
            resource_base_url=static_api_base_url,
            ocw_hugo_themes_branch=themes_branch,
            ocw_hugo_projects_branch=projects_branch,
            sitemap_domain=site_pipeline_vars["sitemap_domain"],
            namespace=namespace,
        )
        course_config.values["ocw_studio_url"] = ""
        across_var_values = [www_config.values, course_config.values]

        site_tasks = []
        site_tasks.extend(
            [
                SiteContentGitTaskStep(
                    branch=site_content_branch,
                    short_id=site_pipeline_vars["short_id"],
                ),
            ]
        )
        site_tasks.extend(
            SitePipelineOnlineTasks(
                pipeline_vars=site_pipeline_vars,
                fastly_var=version,
                skip_cache_clear=True,
            )
        )

        tasks = TestPipelineBaseTasks()
        tasks.append(
            DoStep(
                do=site_tasks,
                across=[
                    AcrossVar(
                        var="site",
                        values=across_var_values,
                        max_in_flight=1,
                    )
                ],
            )
        )
        fetch_built_content_commands = "\n".join(
            [
                "mkdir -p test-sites/tmp/dist/ocw-ci-test-www",
                "mkdir -p test-sites/tmp/dist/courses/",
                f"aws s3{get_cli_endpoint_url()} sync s3://{common_pipeline_vars['test_bucket_name']}/ test-sites/tmp/dist/ocw-ci-test-www/ --exclude *courses/*",  # noqa: E501
                f"aws s3{get_cli_endpoint_url()} sync s3://{common_pipeline_vars['test_bucket_name']}/courses test-sites/tmp/dist/courses/",  # noqa: E501
            ]
        )
        fetch_built_content_step = TaskStep(
            task=fetch_built_content_step_identifier,
            timeout="40m",
            params={
                "AWS_MAX_CONCURRENT_CONNECTIONS": str(
                    settings.AWS_MAX_CONCURRENT_CONNECTIONS
                ),
            },
            config=TaskConfig(
                platform="linux",
                image_resource=AWS_CLI_REGISTRY_IMAGE,
                inputs=[Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER)],
                outputs=[Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER)],
                run=Command(
                    path="sh",
                    dir=OCW_HUGO_THEMES_GIT_IDENTIFIER,
                    args=["-exc", fetch_built_content_commands],
                ),
            ),
        )
        if is_dev():
            fetch_built_content_step.params.update(
                {
                    "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
                    "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
                }
            )
        tasks.append(fetch_built_content_step)
        playwright_commands = "yarn install\nnpx playwright install firefox --with-deps\nnpx playwright install chrome --with-deps\nnpx playwright test"  # noqa: E501
        tasks.append(
            TaskStep(
                task=playwright_task_identifier,
                timeout="20m",
                attempts=3,
                config=TaskConfig(
                    platform="linux",
                    image_resource=PLAYWRIGHT_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                    ],
                    params={
                        "PLAYWRIGHT_BASE_URL": static_api_base_url,
                        "CI": "1",
                        "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
                        "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
                        "OCW_STUDIO_BASE_URL": static_api_base_url,
                        "STATIC_API_BASE_URL": static_api_base_url,
                        "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                        "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                        "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                        "NOINDEX": course_config.values["noindex"],
                        "COURSE_CONTENT_PATH": "../",
                        "COURSE_HUGO_CONFIG_PATH": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/ocw-course-v2/config.yaml",  # noqa: E501
                        "FIELDS_CONTENT_PATH": "",
                        "FIELDS_HUGO_CONFIG_PATH": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/mit-fields/config.yaml",  # noqa: E501
                        "GIT_CONTENT_SOURCE": "git@github.mit.edu:ocw-content-rc",
                        "OCW_TEST_COURSE": course_content_git_identifier,
                        "RESOURCE_BASE_URL": static_api_base_url,
                        "SITEMAP_DOMAIN": site_pipeline_vars["sitemap_domain"],
                        "SEARCH_API_URL": "https://discussions-rc.odl.mit.edu/api/v0/search/",
                        "SENTRY_ENV": "",
                        "WEBPACK_WATCH_MODE": "false",
                        "WWW_CONTENT_PATH": f"../{www_content_git_identifier}",
                        "WWW_HUGO_CONFIG_PATH": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/ocw-www/config.yaml",  # noqa: E501
                    },
                    run=Command(
                        path="sh",
                        dir=OCW_HUGO_THEMES_GIT_IDENTIFIER,
                        args=["-exc", playwright_commands],
                    ),
                ),
            )
        )

        base.__init__(
            resource_types=resource_types,
            resources=resources,
            jobs=[Job(name=test_pipeline_job_identifier, plan=tasks)],
        )
