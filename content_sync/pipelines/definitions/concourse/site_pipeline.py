from typing import Optional

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    DoStep,
    DummyConfig,
    DummyVarSource,
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
    Vars,
    VarSource,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL, TARGET_OFFLINE, TARGET_ONLINE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
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


class TestDummyVarSource(DummyVarSource, VarSource):
    pass


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
        storage_bucket: str,
        artifacts_bucket: str,
        web_bucket: str,
        offline_bucket: str,
        resource_base_url: str,
        ocw_studio_url: str,
        ocw_hugo_themes_branch: str,
        ocw_hugo_projects_branch: str,
        hugo_override_args: Optional[str] = "",
        namespace: str = "site:",
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
        self.storage_bucket_name = storage_bucket
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
        self.namespace = namespace
        self.vars = {
            "short_id": f"(({namespace}short_id))",
            "site_name": f"(({namespace}site_name))",
            "s3_path": f"(({namespace}s3_path))",
            "url_path": f"(({namespace}url_path))",
            "base_url": f"(({namespace}base_url))",
            "static_resources_subdirectory": f"(({namespace}static_resources_subdirectory))",
            "delete_flag": f"(({namespace}delete_flag))",
            "noindex": f"(({namespace}noindex))",
            "pipeline_name": f"(({namespace}pipeline_name))",
            "instance_vars": f"(({namespace}instance_vars))",
            "static_api_url": f"(({namespace}static_api_url))",
            "storage_bucket": f"(({namespace}storage_bucket))",
            "artifacts_bucket": f"(({namespace}artifacts_bucket))",
            "web_bucket": f"(({namespace}web_bucket))",
            "offline_bucket": f"(({namespace}offline_bucket))",
            "resource_base_url": f"(({namespace}resource_base_url))",
            "site_content_branch": f"(({namespace}site_content_branch))",
            "ocw_hugo_themes_branch": f"(({namespace}ocw_hugo_themes_branch))",
            "ocw_hugo_projects_url": f"(({namespace}ocw_hugo_projects_url))",
            "ocw_hugo_projects_branch": f"(({namespace}ocw_hugo_projects_branch))",
            "hugo_args_online": f"(({namespace}hugo_args_online))",
            "hugo_args_offline": f"(({namespace}hugo_args_offline))",
        }
        self.values = {
            "short_id": site.short_id,
            "site_name": site.name,
            "s3_path": site.s3_path,
            "url_path": site.get_url_path(),
            "base_url": self.base_url,
            "static_resources_subdirectory": self.static_resources_subdirectory,
            "delete_flag": self.delete_flag,
            "noindex": self.noindex,
            "pipeline_name": pipeline_name,
            "instance_vars": instance_vars,
            "static_api_url": static_api_url,
            "storage_bucket": storage_bucket,
            "artifacts_bucket": artifacts_bucket,
            "web_bucket": web_bucket,
            "offline_bucket": offline_bucket,
            "resource_base_url": resource_base_url,
            "site_content_branch": site_content_branch,
            "ocw_hugo_themes_branch": ocw_hugo_themes_branch,
            "ocw_hugo_projects_url": self.ocw_hugo_projects_url,
            "ocw_hugo_projects_branch": ocw_hugo_projects_branch,
            "hugo_args_online": hugo_args_online,
            "hugo_args_offline": hugo_args_offline,
        }


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
            name=WEBPACK_MANIFEST_S3_IDENTIFIER,
            bucket=config.vars["artifacts_bucket"],
            branch=config.vars["ocw_hugo_themes_branch"],
        )
        ocw_hugo_themes_resource = OcwHugoThemesGitResource(
            branch=config.vars["ocw_hugo_themes_branch"]
        )
        ocw_hugo_projects_resource = OcwHugoProjectsGitResource(
            uri=config.vars["ocw_hugo_projects_url"],
            branch=config.vars["ocw_hugo_projects_branch"],
        )
        site_content_resource = SiteContentGitResource(
            name=SITE_CONTENT_GIT_IDENTIFIER,
            branch=config.vars["site_content_branch"],
            short_id=config.vars["short_id"],
        )
        ocw_studio_webhook_resource = OcwStudioWebhookResource(
            ocw_studio_url=config.ocw_studio_url,
            site_name=config.vars["site_name"],
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
    def __init__(
        self,
        config: SitePipelineDefinitionConfig,
        gated: bool = False,
        passed_identifier: Identifier = None,
    ):
        webpack_manifest_get_step = add_error_handling(
            step=GetStep(
                get=WEBPACK_MANIFEST_S3_IDENTIFIER,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{WEBPACK_MANIFEST_S3_IDENTIFIER} get step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        ocw_hugo_themes_get_step = add_error_handling(
            step=GetStep(
                get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{OCW_HUGO_THEMES_GIT_IDENTIFIER} get step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        ocw_hugo_projects_get_step = add_error_handling(
            step=GetStep(
                get=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{OCW_HUGO_PROJECTS_GIT_IDENTIFIER} get step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        theme_get_steps = [
            webpack_manifest_get_step,
            ocw_hugo_themes_get_step,
            ocw_hugo_projects_get_step,
        ]
        if gated:
            for get_step in theme_get_steps:
                get_step.passed = [passed_identifier]
        self.extend(theme_get_steps)


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
                get=SITE_CONTENT_GIT_IDENTIFIER,
                trigger=False,
                timeout="5m",
                attempts=3,
            ),
            step_description=f"{SITE_CONTENT_GIT_IDENTIFIER} get step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        static_resources_step = add_error_handling(
            step=TaskStep(
                task=STATIC_RESOURCES_S3_IDENTIFIER,
                timeout="40m",
                attempts=3,
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    outputs=[Output(name=STATIC_RESOURCES_S3_IDENTIFIER)],
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"aws s3{config.cli_endpoint_url} sync s3://{config.vars['storage_bucket']}/{config.vars['s3_path']} ./{STATIC_RESOURCES_S3_IDENTIFIER}",
                        ],
                    ),
                ),
            ),
            step_description=f"{STATIC_RESOURCES_S3_IDENTIFIER} s3 sync to container",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
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
            pipeline_name=config.vars["pipeline_name"],
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
                    "STATIC_API_BASE_URL": config.vars["static_api_url"],
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                    "NOINDEX": config.vars["noindex"],
                },
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                        Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                        Input(name=SITE_CONTENT_GIT_IDENTIFIER),
                        Input(name=STATIC_RESOURCES_S3_IDENTIFIER),
                        Input(name=WEBPACK_MANIFEST_S3_IDENTIFIER),
                    ],
                    outputs=[
                        Output(name=SITE_CONTENT_GIT_IDENTIFIER),
                        Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                    ],
                    run=Command(
                        dir=SITE_CONTENT_GIT_IDENTIFIER,
                        path="sh",
                        args=[
                            "-exc",
                            f"""
                            cp ../{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json ../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/data
                            hugo {config.vars['hugo_args_online']}
                            cp -r -n ../{STATIC_RESOURCES_S3_IDENTIFIER}/. ./output-online{config.vars['static_resources_subdirectory']}
                            rm -rf ./output-online{config.vars['static_resources_subdirectory']}*.mp4
                            """,
                        ],
                    ),
                ),
            ),
            step_description=f"{BUILD_ONLINE_SITE_IDENTIFIER} task step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        if is_dev():
            build_online_site_step.params["RESOURCE_BASE_URL"] = config.vars[
                "resource_base_url"
            ]
            build_online_site_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            build_online_site_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY
        if config.is_root_website:
            online_sync_command = f"aws s3{config.cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{config.vars['web_bucket']}/{config.vars['base_url']} --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        else:
            online_sync_command = f"aws s3{config.cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{config.vars['web_bucket']}/{config.vars['base_url']} --exclude='{config.vars['short_id']}.zip' --exclude='{config.vars['short_id']}-video.zip' --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        upload_online_build_step = add_error_handling(
            step=TaskStep(
                task=UPLOAD_ONLINE_BUILD_IDENTIFIER,
                timeout="40m",
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[Input(name=SITE_CONTENT_GIT_IDENTIFIER)],
                    run=Command(path="sh", args=["-exc", online_sync_command]),
                ),
                on_success=OcwStudioWebhookStep(
                    pipeline_name=config.vars["pipeline_name"],
                    status="succeeded",
                ),
            ),
            step_description=f"{UPLOAD_ONLINE_BUILD_IDENTIFIER} task step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
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
                site_name=config.vars["site_name"],
            ),
            step_description="clear cdn cache",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        clear_cdn_cache_online_step.on_success = TryStep(
            try_=DoStep(
                do=[
                    OpenDiscussionsWebhookStep(
                        site_url=config.vars["url_path"],
                        pipeline_name=config.vars["pipeline_name"],
                    ),
                    OcwStudioWebhookStep(
                        pipeline_name=config.vars["pipeline_name"],
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
                    inputs=[Input(name=WEBPACK_MANIFEST_S3_IDENTIFIER)],
                    outputs=[Output(name=WEBPACK_ARTIFACTS_IDENTIFIER)],
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"jq 'recurse | select(type==\"string\")' ./{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json | tr -d '\"' | xargs -I {{}} aws s3{config.cli_endpoint_url} cp s3://{config.vars['web_bucket']}{{}} ./{WEBPACK_ARTIFACTS_IDENTIFIER}/{{}} --exclude *.js.map",
                        ],
                    ),
                ),
            ),
            step_description=f"{FILTER_WEBPACK_ARTIFACTS_IDENTIFIER} task step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        if is_dev():
            filter_webpack_artifacts_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            filter_webpack_artifacts_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY
        build_offline_site_command = f"""
        cp ../{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json ../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/base-theme/data
        mkdir -p ./content/static_resources
        mkdir -p ./static/static_resources
        mkdir -p ./static/static_shared
        mkdir -p ../videos
        cp -r ../{STATIC_RESOURCES_S3_IDENTIFIER}/. ./content/static_resources
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
        hugo {config.vars['hugo_args_offline']}
        """
        if not config.is_root_website:
            build_offline_site_command = f"""
            {build_offline_site_command}
            cd output-offline
            zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{config.vars['short_id']}.zip ./
            rm -rf ./*
            cd ..
            if [ $MP4_COUNT != 0 ];
            then
                mv ../videos/* ./content/static_resources
            fi
            hugo {config.vars['hugo_args_offline']}
            cd output-offline
            zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{config.vars['short_id']}-video.zip ./
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
                    "STATIC_API_BASE_URL": config.vars["static_api_url"],
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                    "NOINDEX": config.vars["noindex"],
                },
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                        Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                        Input(name=SITE_CONTENT_GIT_IDENTIFIER),
                        Input(name=STATIC_RESOURCES_S3_IDENTIFIER),
                        Input(name=WEBPACK_MANIFEST_S3_IDENTIFIER),
                        Input(name=WEBPACK_ARTIFACTS_IDENTIFIER),
                    ],
                    outputs=[
                        Output(name=SITE_CONTENT_GIT_IDENTIFIER),
                        Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                        Output(name=BUILD_OFFLINE_SITE_IDENTIFIER),
                    ],
                    run=Command(
                        dir=SITE_CONTENT_GIT_IDENTIFIER,
                        path="sh",
                        args=[
                            "-exc",
                            build_offline_site_command,
                        ],
                    ),
                ),
            ),
            step_description=f"{BUILD_OFFLINE_SITE_IDENTIFIER} task step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        if is_dev():
            build_offline_site_step.params["RESOURCE_BASE_URL"] = (
                config.vars["resource_base_url"] or ""
            )
            build_offline_site_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            build_offline_site_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        offline_sync_commands = [
            f"aws s3{config.cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{config.vars['offline_bucket']}/{config.vars['base_url']} --metadata site-id={config.vars['site_name']}{config.vars['delete_flag']}"
        ]
        if not config.is_root_website:
            offline_sync_commands.append(
                f"aws s3{config.cli_endpoint_url} sync {BUILD_OFFLINE_SITE_IDENTIFIER}/ s3://{config.vars['web_bucket']}/{config.vars['base_url']} --exclude='*' --include='{config.vars['short_id']}.zip' --include='{config.vars['short_id']}-video.zip' --metadata site-id={config.vars['site_name']}"
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
                        Input(name=SITE_CONTENT_GIT_IDENTIFIER),
                        Input(name=BUILD_OFFLINE_SITE_IDENTIFIER),
                        Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                    ],
                    run=Command(path="sh", args=["-exc", offline_sync_command]),
                ),
            ),
            step_description=f"{UPLOAD_OFFLINE_BUILD_IDENTIFIER} task step",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
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
                site_name=config.vars["site_name"],
            ),
            step_description="clear cdn cache",
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        clear_cdn_cache_offline_step.on_success = TryStep(
            try_=DoStep(
                do=[
                    OpenDiscussionsWebhookStep(
                        site_url=config.vars["url_path"],
                        pipeline_name=config.vars["pipeline_name"],
                    ),
                    OcwStudioWebhookStep(
                        pipeline_name=config.vars["pipeline_name"],
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
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
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
            pipeline_name=config.vars["pipeline_name"],
            short_id=config.vars["short_id"],
            instance_vars=config.vars["instance_vars"],
        )
        offline_job.plan.insert(0, offline_build_gate_get_step)
        dummy_var_source = DummyVarSource(
            name="site",
            config=DummyConfig(
                vars={
                    "short_id": config.values["short_id"],
                    "site_name": config.values["site_name"],
                    "s3_path": config.values["s3_path"],
                    "url_path": config.values["url_path"],
                    "base_url": config.values["base_url"],
                    "static_resources_subdirectory": config.values[
                        "static_resources_subdirectory"
                    ],
                    "delete_flag": config.values["delete_flag"],
                    "noindex": config.values["noindex"],
                    "pipeline_name": config.values["pipeline_name"],
                    "instance_vars": config.values["instance_vars"],
                    "static_api_url": config.values["static_api_url"],
                    "storage_bucket": config.values["storage_bucket"],
                    "artifacts_bucket": config.values["artifacts_bucket"],
                    "web_bucket": config.values["web_bucket"],
                    "offline_bucket": config.values["offline_bucket"],
                    "resource_base_url": config.values["resource_base_url"],
                    "ocw_studio_url": config.ocw_studio_url,
                    "site_content_branch": config.values["site_content_branch"],
                    "ocw_hugo_themes_branch": config.values["ocw_hugo_themes_branch"],
                    "ocw_hugo_projects_url": config.values["ocw_hugo_projects_url"],
                    "ocw_hugo_projects_branch": config.values[
                        "ocw_hugo_projects_branch"
                    ],
                    "hugo_args_online": config.values["hugo_args_online"],
                    "hugo_args_offline": config.values["hugo_args_offline"],
                }
            ),
        )
        base.__init__(
            var_sources=[dummy_var_source],
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
        steps = SitePipelineThemeTasks(
            config=config,
            gated=True,
            passed_identifier=self._online_site_job_identifier,
        )
        steps.extend(
            SitePipelineOfflineTasks(
                config=config,
                gated=True,
                passed_identifier=self._online_site_job_identifier,
            )
        )
        return Job(
            name=self._offline_site_job_identifier,
            serial=True,
            plan=steps,
        )
