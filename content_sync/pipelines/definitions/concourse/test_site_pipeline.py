import json
from urllib.parse import quote

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    AcrossVar,
    DoStep,
    GetStep,
    Identifier,
    Job,
    Pipeline,
    StepModifierMixin,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
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
    get_common_pipeline_vars,
    get_site_content_branch,
)
from main.utils import is_dev
from websites.models import Website

CLI_ENDPOINT_URL = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""


class TestPipelineBaseTasks(list[StepModifierMixin]):
    """
    The common task objects used in the test pipeline
    """

    def __init__(self):
        webpack_manifest_get_step = GetStep(
            get=WEBPACK_MANIFEST_S3_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
        )
        ocw_hugo_themes_get_step = GetStep(
            get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
        )
        ocw_hugo_projects_get_step = GetStep(
            get=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
        )
        self.extend(
            [
                webpack_manifest_get_step,
                ocw_hugo_themes_get_step,
                ocw_hugo_projects_get_step,
            ]
        )


class TestPipelineDefinition(Pipeline):
    """
    A Pipeline that does the following:

     -
    """

    def __init__(self, themes_branch: str, projects_branch: str, **kwargs):
        base = super()
        base.__init__(**kwargs)
        namespace = ".:site."
        common_pipeline_vars = get_common_pipeline_vars()
        site_pipeline_vars = get_site_pipeline_definition_vars(namespace=namespace)
        prefix = "test"
        version = VERSION_LIVE
        www_slug = "ocw-ci-test-www"
        course_slug = "ocw-ci-test-course"
        test_pipeline_job_identifier = Identifier("e2e-test-job").root
        www_git_identifier = Identifier(www_slug).root
        course_git_identifier = Identifier(course_slug).root
        www_website = Website.objects.get(name=www_slug)
        course_website = Website.objects.get(name=course_slug)
        ocw_hugo_projects_url = www_website.starter.ocw_hugo_projects_url
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
        ocw_hugo_projects_resource = OcwHugoProjectsGitResource(
            uri=ocw_hugo_projects_url,
            branch=projects_branch,
        )
        ocw_studio_webhook_resource = OcwStudioWebhookResource(
            site_name=course_website.name,
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
            site=www_website,
            pipeline_name=version,
            instance_vars=f"?vars={quote(json.dumps({'site': www_website.name}))}",
            site_content_branch=site_content_branch,
            static_api_url=common_pipeline_vars["static_api_base_url_live"],
            storage_bucket=common_pipeline_vars["storage_bucket_name"],
            artifacts_bucket=common_pipeline_vars["artifacts_bucket_name"],
            web_bucket=common_pipeline_vars["publish_bucket_name"],
            offline_bucket=common_pipeline_vars["offline_publish_bucket_name"],
            resource_base_url=common_pipeline_vars["resource_base_url_live"],
            ocw_hugo_themes_branch=themes_branch,
            ocw_hugo_projects_branch=projects_branch,
            namespace=namespace,
            prefix=prefix,
        )
        www_config.is_root_website = True
        www_config.values["is_root_website"] = 1
        www_config.values["delete_flag"] = ""
        www_config.values["url_path"] = ""
        www_config.values["base_url"] = ""
        course_config = SitePipelineDefinitionConfig(
            site=course_website,
            pipeline_name=version,
            instance_vars=f"?vars={quote(json.dumps({'site': course_website.name}))}",
            site_content_branch=site_content_branch,
            static_api_url=common_pipeline_vars["static_api_base_url_live"],
            storage_bucket=common_pipeline_vars["storage_bucket_name"],
            artifacts_bucket=common_pipeline_vars["artifacts_bucket_name"],
            web_bucket=common_pipeline_vars["publish_bucket_name"],
            offline_bucket=common_pipeline_vars["offline_publish_bucket_name"],
            resource_base_url=common_pipeline_vars["resource_base_url_live"],
            ocw_hugo_themes_branch=themes_branch,
            ocw_hugo_projects_branch=projects_branch,
            namespace=namespace,
            prefix=prefix,
        )
        across_var_values = [www_config.values, course_config.values]

        site_tasks = []
        site_tasks.extend(
            [
                SiteContentGitTaskStep(
                    branch=site_content_branch,
                    short_id=www_git_identifier,
                ),
                SiteContentGitTaskStep(
                    branch=site_pipeline_vars["site_content_branch"],
                    short_id=course_git_identifier,
                ),
            ]
        )
        site_tasks.extend(
            SitePipelineOnlineTasks(
                pipeline_vars=site_pipeline_vars,
                fastly_var=version,
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

        base.__init__(
            resource_types=resource_types,
            resources=resources,
            jobs=[Job(name=test_pipeline_job_identifier, plan=tasks)],
        )
