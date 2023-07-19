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
from content_sync.pipelines.definitions.concourse.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.resource_types import (
    HttpResourceType,
    KeyvalResourceType,
    S3IamResourceType,
)
from content_sync.pipelines.definitions.concourse.resources import (
    GitResource,
    OpenDiscussionsResource,
    SlackAlertResource,
)
from content_sync.pipelines.definitions.concourse.steps import (
    ClearCdnCacheStep,
    SlackAlertStep,
)
from main.utils import is_dev
from websites.constants import OCW_HUGO_THEMES_GIT


CLI_ENDPOINT_URL = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""


class ThemeAssetsPipelineDefinition(Pipeline):
    http_resource_type = HttpResourceType()
    keyval_resource_type = KeyvalResourceType()
    s3_iam_resource_type = S3IamResourceType()

    build_theme_assets_job_identifier = Identifier("build-theme-assets")
    ocw_hugo_themes_identifier = Identifier("ocw-hugo-themes")
    build_ocw_hugo_themes_identifier = Identifier("build-ocw-hugo-themes")
    copy_s3_buckets_identifier = Identifier("copy-s3-buckets")
    clear_cdn_cache_draft_identifier = Identifier("clear-cdn-cache-draft")
    clear_cdn_cache_live_identifier = Identifier("clear-cdn-cache-live")

    open_discussions_resource = OpenDiscussionsResource()
    slack_resource = SlackAlertResource()

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        artifacts_bucket: str,
        preview_bucket: str,
        publish_bucket: str,
        ocw_hugo_themes_branch: str,
        **kwargs,
    ):
        base = super()
        base.__init__(**kwargs)
        ocw_hugo_themes_resource = GitResource(
            name=self.ocw_hugo_themes_identifier,
            uri=OCW_HUGO_THEMES_GIT,
            branch=ocw_hugo_themes_branch,
        )
        resource_types = []
        resources = [ocw_hugo_themes_resource]
        tasks = [
            GetStep(
                get=self.ocw_hugo_themes_identifier,
                trigger=(not is_dev()),
            ),
            TaskStep(
                task=self.build_ocw_hugo_themes_identifier,
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[Input(name=self.ocw_hugo_themes_identifier)],
                    outputs=[Output(name=self.ocw_hugo_themes_identifier)],
                    params={
                        "SEARCH_API_URL": settings.SEARCH_API_URL,
                        "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                        "SENTRY_ENV": settings.ENVIRONMENT,
                    },
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            """
                            cd ocw-hugo-themes
                            yarn install --immutable
                            npm run build:webpack
                            npm run build:githash
                            """,
                        ],
                    ),
                ),
            ),
            TaskStep(
                task=self.copy_s3_buckets_identifier,
                timeout="20m",
                attempts=3,
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[Input(name=self.ocw_hugo_themes_identifier)],
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
                            aws s3{CLI_ENDPOINT_URL} cp ocw-hugo-themes/base-theme/dist s3://{preview_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp ocw-hugo-themes/base-theme/dist s3://{publish_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp ocw-hugo-themes/base-theme/static s3://{preview_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp ocw-hugo-themes/base-theme/static s3://{publish_bucket} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{CLI_ENDPOINT_URL} cp ocw-hugo-themes/base-theme/data/webpack.json s3://{artifacts_bucket}/ocw-hugo-themes/{ocw_hugo_themes_branch}/webpack.json --metadata site-id=ocw-hugo-themes
                            """,
                        ],
                    ),
                ),
            ),
        ]
        job = Job(name=self.build_theme_assets_job_identifier, serial=True)
        if not is_dev():
            resource_types.append(slack_notification_resource)
            resources.append(self.slack_resource)
            tasks.append(
                ClearCdnCacheStep(
                    name=self.clear_cdn_cache_draft_identifier,
                    fastly_var="fastly_draft",
                    purge_url="purge/ocw-hugo-themes",
                )
            )
            tasks.append(
                ClearCdnCacheStep(
                    name=self.clear_cdn_cache_live_identifier,
                    fastly_var="fastly_live",
                    purge_url="purge/ocw-hugo-themes",
                )
            )
            job.on_failure = SlackAlertStep(
                alert_type="failed",
                text=f"""
                Failed to build theme assets.

                Append `?vars.branch={ocw_hugo_themes_branch}` to the url below for more details.
                """,
            )
            job.on_abort = SlackAlertStep(
                alert_type="aborted",
                text=f"""
                User aborted while building theme assets.

                Append `?vars.branch={ocw_hugo_themes_branch}` to the url below for more details.
                """,
            )

        job.plan = tasks
        base.__init__(
            resource_types=resource_types, resources=resources, jobs=[job], **kwargs
        )
