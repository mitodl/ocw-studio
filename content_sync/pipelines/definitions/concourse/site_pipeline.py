from typing import Optional
from urllib.parse import urljoin, urlparse

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    DoStep,
    GetStep,
    Identifier,
    Input,
    Job,
    Output,
    Pipeline,
    PutStep,
    Resource,
    ResourceType,
    StepModifierMixin,
    TaskConfig,
    TaskStep,
    TryStep,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, TARGET_OFFLINE, TARGET_ONLINE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
    STATIC_RESOURCES_S3_IDENTIFIER,
    WEBPACK_ARTIFACTS_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.common.resource_types import (
    HttpResourceType,
    KeyvalResourceType,
    S3IamResourceType,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    OcwHugoProjectsGitResource,
    OcwHugoThemesGitResource,
    OcwStudioWebhookResource,
    OpenDiscussionsResource,
    SiteContentGitResource,
    SlackAlertResource,
    WebpackManifestResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    OcwStudioWebhookStep,
    OpenDiscussionsWebhookStep,
    add_error_handling,
)
from content_sync.utils import get_hugo_arg_string
from main.constants import PRODUCTION_NAMES
from main.utils import is_dev
from websites.models import Website


BUILD_ONLINE_SITE_IDENTIFIER = Identifier("build-online-site").root
UPLOAD_ONLINE_BUILD_IDENTIFIER = Identifier("upload-online-build").root
FILTER_WEBPACK_ARTIFACTS_IDENTIFIER = Identifier("filter-webpack-artifacts").root
BUILD_OFFLINE_SITE_IDENTIFIER = Identifier("build-offline-site").root
UPLOAD_OFFLINE_BUILD_IDENTIFIER = Identifier("upload-offline-build").root
CLEAR_CDN_CACHE_IDENTIFIER = Identifier("clear-cdn-cache").root


class SitePipelineDefinitionConfig:
    """
    A class with configuration properties for building a site pipeline

    Args:
        site(Website): The Website object to build the pipeline for
        pipeline_name(str): The pipeline name to use in Concourse (draft / live)
        instance_vars(str): The instance vars for the pipeline in a query string format
        site_content_branch(str): The branch to use in the site content repo (preview / release)
        static_api_url(str): The base URL for fetching JSON files from the static API (https://ocw.mit.edu/)
        storage_bucket_name(str): The bucket name ocw-studio stores resources in (ol-ocw-studio-app)
        artifacts_bucket(str): The versioned bucket where the webpack manifest is stored (ol-eng-artifacts)
        web_bucket(str): The online bucket to publish output to (ocw-content-draft)
        offline_bucket(str): The offline bucket to publish output to (ocw-content-offline-draft)
        resource_base_url(str): A base URL to override fetching of resources from
        ocw_studio_url(str): The URL to the instance of ocw-studio the pipeline should call home to
        ocw_hugo_themes_branch(str): The branch of ocw-hugo-themes to use
        ocw_hugo_projects_branch(str): The branch of ocw-hugo-projects to use
        hugo_override_args(str): Arguments to override in the hugo command
    """

    def __init__(
        self,
        site: Website,
        pipeline_name: str,
        instance_vars: str,
        site_content_branch: str,
        static_api_url: str,
        storage_bucket_name: str,
        artifacts_bucket: str,
        web_bucket: str,
        offline_bucket: str,
        resource_base_url: str,
        ocw_studio_url: str,
        ocw_hugo_themes_branch: str,
        ocw_hugo_projects_branch: str,
        hugo_override_args: Optional[str] = "",
    ):
        self.site = site
        self.pipeline_name = pipeline_name
        self.is_root_website = site.name == settings.ROOT_WEBSITE_NAME
        if self.is_root_website:
            self.base_url = ""
            self.static_resources_subdirectory = f"/{site.get_url_path()}/"
            self.delete_flag = ""
        else:
            self.base_url = site.get_url_path()
            self.static_resources_subdirectory = "/"
            self.delete_flag = " --delete"
        self.site_content_branch = site_content_branch
        self.pipeline_name = pipeline_name
        self.static_api_url = static_api_url
        self.storage_bucket_name = storage_bucket_name
        self.artifacts_bucket = artifacts_bucket
        self.web_bucket = web_bucket
        self.offline_bucket = offline_bucket
        self.resource_base_url = resource_base_url
        if (
            self.site_content_branch == "preview"
            or settings.ENV_NAME not in PRODUCTION_NAMES
        ):
            self.noindex = "true"
        else:
            self.noindex = "false"
        self.ocw_studio_url = ocw_studio_url
        self.ocw_hugo_themes_branch = ocw_hugo_themes_branch
        self.ocw_hugo_projects_url = site.starter.ocw_hugo_projects_url
        self.ocw_hugo_projects_branch = ocw_hugo_projects_branch
        starter_slug = site.starter.slug
        base_hugo_args = {"--themesDir": f"../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/"}
        base_online_args = base_hugo_args.copy()
        base_online_args.update(
            {
                "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config.yaml",
                "--baseURL": f"/{self.base_url}",
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
            pipeline_name,
            base_online_args,
            hugo_override_args,
        )
        hugo_args_offline = get_hugo_arg_string(
            TARGET_OFFLINE,
            pipeline_name,
            base_offline_args,
            hugo_override_args,
        )
        self.hugo_args_online = hugo_args_online
        self.hugo_args_offline = hugo_args_offline
        self.instance_vars = instance_vars
        self.cli_endpoint_url = (
            f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""
        )
        self.webpack_manifest_s3_identifier = Identifier(
            f"{WEBPACK_MANIFEST_S3_IDENTIFIER}-{ocw_hugo_themes_branch}"
        ).root
        self.site_content_git_identifier = Identifier(
            f"{SITE_CONTENT_GIT_IDENTIFIER}-{site.short_id.lower()}"
        ).root
        self.static_resources_s3_identifier = Identifier(
            f"{STATIC_RESOURCES_S3_IDENTIFIER}-{site.short_id.lower()}"
        )
        self.ocw_studio_webhook_identifier = Identifier(
            f"{OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER}-{site.short_id.lower()}"
        ).root


class SitePipelineResourceTypes(list[ResourceType]):
    """
    The ResourceType objects used in a site pipeline
    """

    def __init__(self):
        self.extend(
            [
                HttpResourceType(),
                S3IamResourceType(),
                slack_notification_resource(),
            ]
        )


class SitePipelineResources(list[Resource]):
    """
    The Resource objects used in a site pipeline

    Args:
        config(SitePipelineDefinitionConfig): The site pipeline configuration object
    """

    def __init__(self, config: SitePipelineDefinitionConfig):
        webpack_manifest_resource = WebpackManifestResource(
            name=config.webpack_manifest_s3_identifier,
            bucket=config.artifacts_bucket,
            branch=config.ocw_hugo_themes_branch,
        )
        ocw_hugo_themes_resource = OcwHugoThemesGitResource(
            branch=config.ocw_hugo_themes_branch
        )
        ocw_hugo_projects_resource = OcwHugoProjectsGitResource(
            uri=config.ocw_hugo_projects_url, branch=config.ocw_hugo_projects_branch
        )
        site_content_resource = SiteContentGitResource(
            name=config.site_content_git_identifier,
            branch=config.site_content_branch,
            short_id=config.site.short_id.lower(),
        )
        ocw_studio_webhook_resource = OcwStudioWebhookResource(
            ocw_studio_url=config.ocw_studio_url,
            site_name=config.site.name,
            short_id=config.site.short_id.lower(),
            api_token=settings.API_BEARER_TOKEN or "",
        )
        self.extend(
            [
                webpack_manifest_resource,
                site_content_resource,
                ocw_hugo_themes_resource,
                ocw_hugo_projects_resource,
                ocw_studio_webhook_resource,
                SlackAlertResource(),
            ]
        )
        if not is_dev():
            self.append(OpenDiscussionsResource())


class SitePipelineThemeTasks(list[StepModifierMixin]):
    def __init__(self, config: SitePipelineDefinitionConfig):    
        webpack_manifest_get_step = add_error_handling(
            step=GetStep(
                get=config.webpack_manifest_s3_identifier,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{config.webpack_manifest_s3_identifier} get step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        ocw_hugo_themes_get_step = add_error_handling(
            step=GetStep(
                get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{OCW_HUGO_THEMES_GIT_IDENTIFIER} get step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        ocw_hugo_projects_get_step = add_error_handling(
            step=GetStep(
                get=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{OCW_HUGO_PROJECTS_GIT_IDENTIFIER} get step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        self.extend([
            webpack_manifest_get_step,
            ocw_hugo_themes_get_step,
            ocw_hugo_projects_get_step
        ])

class SitePipelineBaseTasks(list[StepModifierMixin]):
    """
    The base tasks used in a site pipeline

    Args:
        config(SitePipelineDefinitionConfig): The site pipeline configuration object
    """

    def __init__(
        self,
        config: SitePipelineDefinitionConfig,
        gated: bool = False,
        passed_identifier: Identifier = None,
    ):
        site_content_get_step = add_error_handling(
            step=GetStep(
                get=config.site_content_git_identifier,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{config.site_content_git_identifier} get step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        static_resources_step = add_error_handling(
            step=TaskStep(
                task=config.static_resources_s3_identifier,
                timeout="40m",
                attempts=3,
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    outputs=[Output(name=config.static_resources_s3_identifier)],
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"aws s3{config.cli_endpoint_url} sync s3://{config.storage_bucket_name}/{config.site.s3_path} ./{config.static_resources_s3_identifier}",
                        ],
                    ),
                ),
            ),
            step_description=f"{config.static_resources_s3_identifier} s3 sync to container",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        if is_dev():
            static_resources_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            static_resources_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        get_steps = [
            site_content_get_step,
        ]
        if gated:
            for get_step in get_steps:
                get_step.passed = [passed_identifier]
        self.extend(get_steps)
        self.append(static_resources_step)


class SitePipelineOnlineTasks(list[StepModifierMixin]):
    """
    The tasks used in the online site job

    Args:
        config(SitePipelineDefinitionConfig): The site pipeline configuration object
    """

    def __init__(self, config: SitePipelineDefinitionConfig):
        base_tasks = SitePipelineBaseTasks(config=config)
        ocw_studio_webhook_started_step = OcwStudioWebhookStep(
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            status="started",
        )
        build_online_site_step = add_error_handling(
            step=TaskStep(
                task=BUILD_ONLINE_SITE_IDENTIFIER,
                timeout="20m",
                attempts=3,
                params={
                    "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
                    "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
                    "OCW_STUDIO_BASE_URL": config.ocw_studio_url,
                    "STATIC_API_BASE_URL": config.static_api_url,
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                    "NOINDEX": config.noindex,
                },
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                        Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                        Input(name=config.site_content_git_identifier),
                        Input(name=config.static_resources_s3_identifier),
                        Input(name=config.webpack_manifest_s3_identifier),
                    ],
                    outputs=[
                        Output(name=config.site_content_git_identifier),
                        Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                    ],
                    run=Command(
                        dir=config.site_content_git_identifier,
                        path="sh",
                        args=[
                            "-exc",
                            f"""
                            cp ../{config.webpack_manifest_s3_identifier}/webpack.json ../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/data
                            hugo {config.hugo_args_online}
                            cp -r -n ../{config.static_resources_s3_identifier}/. ./output-online{config.static_resources_subdirectory}
                            rm -rf ./output-online{config.static_resources_subdirectory}*.mp4
                            """,
                        ],
                    ),
                ),
            ),
            step_description=f"{BUILD_ONLINE_SITE_IDENTIFIER} task step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        if is_dev():
            build_online_site_step.params[
                "RESOURCE_BASE_URL"
            ] = config.resource_base_url
            build_online_site_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            build_online_site_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY
        if config.is_root_website:
            online_sync_command = f"aws s3{config.cli_endpoint_url} sync {config.site_content_git_identifier}/output-online s3://{config.web_bucket}/{config.base_url} --metadata site-id={config.site.name}{config.delete_flag}"
        else:
            online_sync_command = f"aws s3{config.cli_endpoint_url} sync {config.site_content_git_identifier}/output-online s3://{config.web_bucket}/{config.base_url} --exclude='{config.site.short_id.lower()}.zip' --exclude='{config.site.short_id.lower()}-video.zip' --metadata site-id={config.site.name}{config.delete_flag}"
        upload_online_build_step = add_error_handling(
            step=TaskStep(
                task=UPLOAD_ONLINE_BUILD_IDENTIFIER,
                timeout="40m",
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[Input(name=config.site_content_git_identifier)],
                    run=Command(path="sh", args=["-exc", online_sync_command]),
                ),
                on_success=OcwStudioWebhookStep(
                    pipeline_name=config.pipeline_name,
                    short_id=config.site.short_id.lower(),
                    status="succeeded",
                ),
            ),
            step_description=f"{UPLOAD_ONLINE_BUILD_IDENTIFIER} task step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        if is_dev():
            upload_online_build_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            upload_online_build_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        clear_cdn_cache_online_step = add_error_handling(
            step=ClearCdnCacheStep(
                name=CLEAR_CDN_CACHE_IDENTIFIER,
                fastly_var="fastly",
                site_name=config.site.name,
            ),
            step_description="clear cdn cache",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        clear_cdn_cache_online_step.on_success = TryStep(
            try_=DoStep(
                do=[
                    OpenDiscussionsWebhookStep(
                        site_url=config.site.get_url_path(),
                        pipeline_name=config.pipeline_name,
                    ),
                    OcwStudioWebhookStep(
                        pipeline_name=config.pipeline_name,
                        short_id=config.site.short_id.lower(),
                        status="succeeded",
                    ),
                ]
            )
        )
        self.append(ocw_studio_webhook_started_step)
        self.extend(base_tasks)
        self.extend([build_online_site_step, upload_online_build_step])
        if not is_dev():
            self.append(clear_cdn_cache_online_step)


class SitePipelineOfflineTasks(list[StepModifierMixin]):
    """
    The tasks used in the offline site job

    Args:
        config(SitePipelineDefinitionConfig): The site pipeline configuration object
    """

    def __init__(
        self,
        config: SitePipelineDefinitionConfig,
        gated: bool = False,
        passed_identifier: str = None,
    ):
        base_tasks = SitePipelineBaseTasks(
            config=config,
            gated=gated,
            passed_identifier=passed_identifier,
        )
        filter_webpack_artifacts_step = add_error_handling(
            step=TaskStep(
                task=FILTER_WEBPACK_ARTIFACTS_IDENTIFIER,
                timeout="10m",
                attempts=3,
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[Input(name=config.webpack_manifest_s3_identifier)],
                    outputs=[Output(name=WEBPACK_ARTIFACTS_IDENTIFIER)],
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"jq 'recurse | select(type==\"string\")' ./{config.webpack_manifest_s3_identifier}/webpack.json | tr -d '\"' | xargs -I {{}} aws s3{config.cli_endpoint_url} cp s3://{config.web_bucket}{{}} ./{WEBPACK_ARTIFACTS_IDENTIFIER}/{{}} --exclude *.js.map",
                        ],
                    ),
                ),
            ),
            step_description=f"{FILTER_WEBPACK_ARTIFACTS_IDENTIFIER} task step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        if is_dev():
            filter_webpack_artifacts_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            filter_webpack_artifacts_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY
        build_offline_site_command = f"""
        cp ../{config.webpack_manifest_s3_identifier}/webpack.json ../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/data
        mkdir -p ./content/static_resources
        mkdir -p ./static/static_resources
        mkdir -p ./static/static_shared
        mkdir -p ../videos
        cp -r ../{config.static_resources_s3_identifier}/. ./content/static_resources
        HTML_COUNT="$(ls -1 ./content/static_resources/*.html 2>/dev/null | wc -l)"
        if [ $HTML_COUNT != 0 ];
        then
        mv ./content/static_resources/*.html ./static/static_resources
        fi
        MP4_COUNT="$(ls -1 ./content/static_resources/*.mp4 2>/dev/null | wc -l)"
        if [ $MP4_COUNT != 0 ];
        then
        mv ./content/static_resources/*.mp4 ../videos
        fi
        touch ./content/static_resources/_index.md
        cp -r ../{WEBPACK_ARTIFACTS_IDENTIFIER}/static_shared/. ./static/static_shared/
        hugo {config.hugo_args_offline}
        """
        if not config.is_root_website:
            build_offline_site_command = f"""
            {build_offline_site_command}
            cd output-offline
            zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{config.site.short_id.lower()}.zip ./
            rm -rf ./*
            cd ..
            if [ $MP4_COUNT != 0 ];
            then
                mv ../videos/* ./content/static_resources
            fi
            hugo {config.hugo_args_offline}
            cd output-offline
            zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{config.site.short_id.lower()}-video.zip ./
            """
        build_offline_site_step = add_error_handling(
            step=TaskStep(
                task=BUILD_OFFLINE_SITE_IDENTIFIER,
                timeout="20m",
                attempts=3,
                params={
                    "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
                    "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
                    "OCW_STUDIO_BASE_URL": config.ocw_studio_url,
                    "STATIC_API_BASE_URL": config.static_api_url,
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                    "NOINDEX": config.noindex,
                },
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                        Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                        Input(name=config.site_content_git_identifier),
                        Input(name=config.static_resources_s3_identifier),
                        Input(name=config.webpack_manifest_s3_identifier),
                        Input(name=WEBPACK_ARTIFACTS_IDENTIFIER),
                    ],
                    outputs=[
                        Output(name=config.site_content_git_identifier),
                        Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                        Output(name=BUILD_OFFLINE_SITE_IDENTIFIER),
                    ],
                    run=Command(
                        dir=config.site_content_git_identifier,
                        path="sh",
                        args=[
                            "-exc",
                            build_offline_site_command,
                        ],
                    ),
                ),
            ),
            step_description=f"{BUILD_OFFLINE_SITE_IDENTIFIER} task step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        if is_dev():
            build_offline_site_step.params["RESOURCE_BASE_URL"] = (
                config.resource_base_url or ""
            )
            build_offline_site_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            build_offline_site_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        offline_sync_commands = [
            f"aws s3{config.cli_endpoint_url} sync {config.site_content_git_identifier}/output-offline/ s3://{config.offline_bucket}/{config.base_url} --metadata site-id={config.site.name}{config.delete_flag}"
        ]
        if not config.is_root_website:
            offline_sync_commands.append(
                f"aws s3{config.cli_endpoint_url} sync {BUILD_OFFLINE_SITE_IDENTIFIER}/ s3://{config.web_bucket}/{config.base_url} --exclude='*' --include='{config.site.short_id.lower()}.zip' --include='{config.site.short_id.lower()}-video.zip' --metadata site-id={config.site.name}"
            )
        offline_sync_command = "\n".join(offline_sync_commands)
        upload_offline_build_step = add_error_handling(
            step=TaskStep(
                task=UPLOAD_OFFLINE_BUILD_IDENTIFIER,
                timeout="40m",
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=config.site_content_git_identifier),
                        Input(name=BUILD_OFFLINE_SITE_IDENTIFIER),
                        Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                    ],
                    run=Command(path="sh", args=["-exc", offline_sync_command]),
                ),
            ),
            step_description=f"{UPLOAD_OFFLINE_BUILD_IDENTIFIER} task step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        if is_dev():
            upload_offline_build_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            upload_offline_build_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY
        clear_cdn_cache_offline_step = add_error_handling(
            ClearCdnCacheStep(
                name=CLEAR_CDN_CACHE_IDENTIFIER,
                fastly_var="fastly",
                site_name=config.site.name,
            ),
            step_description="clear cdn cache",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        clear_cdn_cache_offline_step.on_success = TryStep(
            try_=DoStep(
                do=[
                    OpenDiscussionsWebhookStep(
                        site_url=config.site.get_url_path(),
                        pipeline_name=config.pipeline_name,
                    ),
                    OcwStudioWebhookStep(
                        pipeline_name=config.pipeline_name,
                        short_id=config.site.short_id.lower(),
                        status="succeeded",
                    ),
                ]
            )
        )
        self.extend(base_tasks)
        self.extend(
            [
                filter_webpack_artifacts_step,
                build_offline_site_step,
                upload_offline_build_step,
            ]
        )
        if not is_dev():
            self.append(clear_cdn_cache_offline_step)


class SitePipelineDefinition(Pipeline):
    """
    The Pipeline object representing an individual site pipeline

    Args:
        config(SitePipelineDefinitionConfig): The site pipeline configuration object
    """

    _offline_build_gate_identifier = Identifier("offline-build-gate").root
    _online_site_job_identifier = Identifier("online-site-job").root
    _offline_site_job_identifier = Identifier("offline-site-job").root

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: SitePipelineDefinitionConfig, **kwargs):
        base = super()
        base.__init__(**kwargs)
        resource_types = SitePipelineResourceTypes()
        resource_types.append(KeyvalResourceType())
        resources = SitePipelineResources(config=config)
        offline_build_gate_resource = Resource(
            name=self._offline_build_gate_identifier,
            type=KEYVAL_RESOURCE_TYPE_IDENTIFIER,
            icon="gate",
            check_every="never",
        )
        resources.append(offline_build_gate_resource)
        online_job = self.get_online_build_job(config=config)
        offline_build_gate_put_step = add_error_handling(
            step=PutStep(
                put=self._offline_build_gate_identifier,
                params={"mapping": "timestamp = now()"},
            ),
            step_description=f"{self._offline_build_gate_identifier} task step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        online_job.plan.append(offline_build_gate_put_step)
        offline_job = self.get_offline_build_job(config=config)
        offline_build_gate_get_step = add_error_handling(
            step=GetStep(
                get=self._offline_build_gate_identifier,
                passed=[self._online_site_job_identifier],
                trigger=True,
            ),
            step_description=f"{self._offline_build_gate_identifier} get step",
            pipeline_name=config.pipeline_name,
            short_id=config.site.short_id.lower(),
            instance_vars=config.instance_vars,
        )
        offline_job.plan.insert(0, offline_build_gate_get_step)
        base.__init__(
            resource_types=resource_types,
            resources=resources,
            jobs=[online_job, offline_job],
            **kwargs,
        )

    def get_online_build_job(self, config: SitePipelineDefinitionConfig):
        steps = SitePipelineThemeTasks(config=config)
        steps.extend(SitePipelineOnlineTasks(config=config))
        return Job(
            name=self._online_site_job_identifier,
            serial=True,
            plan=steps,
        )

    def get_offline_build_job(self, config: SitePipelineDefinitionConfig):
        steps = SitePipelineThemeTasks(config=config)
        steps.extend(SitePipelineOfflineTasks(
            config=config,
            gated=True,
            passed_identifier=self._online_site_job_identifier,
        ))
        return Job(
            name=self._offline_site_job_identifier,
            serial=True,
            plan=steps,
        )
