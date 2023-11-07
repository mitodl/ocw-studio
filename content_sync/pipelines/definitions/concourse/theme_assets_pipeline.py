from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    GetStep,
    Identifier,
    Input,
    Job,
    Output,
    Pipeline,
    TaskConfig,
    TaskStep,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    GitResource,
    OpenDiscussionsResource,
    SlackAlertResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    SlackAlertStep,
)
from main.utils import is_dev
from websites.constants import OCW_HUGO_THEMES_GIT

CLI_ENDPOINT_URL = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""


class ThemeAssetsPipelineDefinition(Pipeline):
    """
    A Pipeline that does the following:

     - Fetch the ocw-hugo-themes git repository
     - Run the Webpack build in ocw-hugo-themes
     - Upload the Webpack manifest (webpack.json) to artifacts_bucket
     - Upload the output to preview_bucket and publish_bucket

    Args:
        artifacts_bucket(str): An S3 bucket with versioning enabled for storing the Webpack manifest
        preview_bucket(str): The S3 bucket where preview sites are to be stored
        publish_bucket(str): The S3 bucket where published sites are to be stored
        test_bucket(str): The S3 bucket where test sites are to be stored
        ocw_hugo_themes_branch(str): The branch of ocw-hugo-themes to clone
        instance_vars:(str): Instance vars for the pipeline in query string format
    """  # noqa: E501

    _build_theme_assets_job_identifier = Identifier("build-theme-assets-job").root
    _build_ocw_hugo_themes_identifier = Identifier("build-ocw-hugo-themes-task").root
    _upload_theme_assets_task_identifier = Identifier("upload-theme-assets-task").root
    _clear_draft_cdn_cache_task_identifier = Identifier(
        "clear-draft-cdn-cache-task"
    ).root
    _clear_live_cdn_cache_identifier = Identifier("clear-live-cdn-cache-task").root

    _open_discussions_resource = OpenDiscussionsResource()
    _slack_resource = SlackAlertResource()

    def __init__(  # noqa: PLR0913
        self,
        artifacts_bucket: str,
        preview_bucket: str,
        publish_bucket: str,
        test_bucket: str,
        ocw_hugo_themes_branch: str,
        **kwargs,
    ):
        base = super()
        base.__init__(**kwargs)
        ocw_hugo_themes_resource = GitResource(
            name=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            uri=OCW_HUGO_THEMES_GIT,
            branch=ocw_hugo_themes_branch,
        )
        resource_types = []
        resources = [ocw_hugo_themes_resource]
        tasks = [
            GetStep(
                get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
                trigger=(not is_dev()),
            ),
            TaskStep(
                task=self._build_ocw_hugo_themes_identifier,
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER)],
                    outputs=[Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER)],
                    params={
                        "SEARCH_API_URL": settings.SEARCH_API_URL,
                        "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                        "SENTRY_ENV": settings.ENVIRONMENT,
                    },
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"""
                            cd {OCW_HUGO_THEMES_GIT_IDENTIFIER}
                            yarn install --immutable
                            npm run build:webpack
                            npm run build:githash
                            """,
                        ],
                    ),
                ),
            ),
            TaskStep(
                task=self._upload_theme_assets_task_identifier,
                timeout="20m",
                attempts=3,
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER)],
                    params=(
                        {}
                        if not is_dev()
                        else {
                            "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID or "",
                            "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY
                            or "",
                        }
                    ),
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"""
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/dist s3://{preview_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/dist s3://{publish_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/dist s3://{test_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/static s3://{preview_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/static s3://{publish_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/static s3://{test_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp {OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/data/webpack.json s3://{artifacts_bucket}/ocw-hugo-themes/{ocw_hugo_themes_branch}/webpack.json --metadata site-id=ocw-hugo-themes
                            """,  # noqa: E501
                        ],
                    ),
                ),
            ),
        ]
        job = Job(name=self._build_theme_assets_job_identifier, serial=True)
        if not is_dev():
            resource_types.append(slack_notification_resource())
            resources.append(self._slack_resource)
            tasks.extend(
                [
                    ClearCdnCacheStep(
                        name=self._clear_draft_cdn_cache_task_identifier,
                        fastly_var="fastly_draft",
                        site_name="ocw-hugo-themes",
                    ),
                    ClearCdnCacheStep(
                        name=self._clear_live_cdn_cache_identifier,
                        fastly_var="fastly_live",
                        site_name="ocw-hugo-themes",
                    ),
                ]
            )
            job.on_failure = SlackAlertStep(
                alert_type="failed",
                text=f"""
                Failed to build theme assets.

                Append `?vars.branch={ocw_hugo_themes_branch}` to the url below for more details.
                """,  # noqa: E501
            )
            job.on_abort = SlackAlertStep(
                alert_type="aborted",
                text=f"""
                User aborted while building theme assets.

                Append `?vars.branch={ocw_hugo_themes_branch}` to the url below for more details.
                """,  # noqa: E501
            )

        job.plan = tasks
        base.__init__(
            resource_types=resource_types, resources=resources, jobs=[job], **kwargs
        )
