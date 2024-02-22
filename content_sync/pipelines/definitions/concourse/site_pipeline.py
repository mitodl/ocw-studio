from typing import Optional
from urllib.parse import urlparse

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
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_TEST_URL, TARGET_OFFLINE, TARGET_ONLINE
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
    OpenCatalogResource,
    SiteContentGitResource,
    SlackAlertResource,
    WebpackManifestResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    OcwStudioWebhookStep,
    OpenCatalogWebhookStep,
    add_error_handling,
)
from content_sync.utils import (
    get_cli_endpoint_url,
    get_hugo_arg_string,
    get_ocw_studio_api_url,
)
from main.constants import PRODUCTION_NAMES
from main.utils import is_dev
from websites.models import Website
from websites.utils import is_test_site

BUILD_ONLINE_SITE_IDENTIFIER = Identifier("build-online-site").root
UPLOAD_ONLINE_BUILD_IDENTIFIER = Identifier("upload-online-build").root
FILTER_WEBPACK_ARTIFACTS_IDENTIFIER = Identifier("filter-webpack-artifacts").root
BUILD_OFFLINE_SITE_IDENTIFIER = Identifier("build-offline-site").root
UPLOAD_OFFLINE_BUILD_IDENTIFIER = Identifier("upload-offline-build").root
CLEAR_CDN_CACHE_IDENTIFIER = Identifier("clear-cdn-cache").root


def get_site_pipeline_definition_vars(namespace: str):
    return {
        "is_root_website": f"(({namespace}is_root_website))",
        "short_id": f"(({namespace}short_id))",
        "site_name": f"(({namespace}site_name))",
        "s3_path": f"(({namespace}s3_path))",
        "url_path": f"(({namespace}url_path))",
        "base_url": f"(({namespace}base_url))",
        "static_resources_subdirectory": f"(({namespace}static_resources_subdirectory))",  # noqa: E501
        "delete_flag": f"(({namespace}delete_flag))",
        "noindex": f"(({namespace}noindex))",
        "pipeline_name": f"(({namespace}pipeline_name))",
        "instance_vars": f"(({namespace}instance_vars))",
        "sitemap_domain": f"(({namespace}sitemap_domain))",
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
        "ocw_studio_url": f"(({namespace}ocw_studio_url))",
        "hugo_args_online": f"(({namespace}hugo_args_online))",
        "hugo_args_offline": f"(({namespace}hugo_args_offline))",
        "prefix": f"(({namespace}prefix))",
    }


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
        ocw_hugo_themes_branch(str): The branch of ocw-hugo-themes to use
        ocw_hugo_projects_branch(str): The branch of ocw-hugo-projects to use
        hugo_override_args(str): (Optional) Arguments to override in the hugo command
        prefix(str): (Optional) A prefix to deploy the site at
        namespace(str): The Concourse vars namespace to use
    """  # noqa: E501

    def __init__(  # noqa: PLR0913 PLR0915
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
        ocw_hugo_themes_branch: str,
        ocw_hugo_projects_branch: str,
        hugo_override_args: Optional[str] = "",
        sitemap_domain: Optional[str] = settings.SITEMAP_DOMAIN,
        prefix: str = "",
        namespace: str = "site:",
    ):
        self.site = site
        self.pipeline_name = pipeline_name
        self.is_root_website = site.name in [
            settings.ROOT_WEBSITE_NAME,
            settings.TEST_ROOT_WEBSITE_NAME,
        ]
        self.is_test_website = site.name in settings.OCW_TEST_SITE_SLUGS
        self.site_content_branch = site_content_branch
        self.storage_bucket_name = storage_bucket
        self.artifacts_bucket = artifacts_bucket
        self.web_bucket = web_bucket
        self.offline_bucket = offline_bucket
        self.static_api_url = static_api_url
        self.sitemap_domain = sitemap_domain
        self.url_path = site.get_url_path()
        self.resource_base_url = resource_base_url
        self.ocw_studio_url = get_ocw_studio_api_url()
        if (
            self.site_content_branch == settings.GIT_BRANCH_PREVIEW
            or settings.ENV_NAME not in PRODUCTION_NAMES
        ):
            self.noindex = "true"
        else:
            self.noindex = "false"
        self.ocw_hugo_themes_branch = ocw_hugo_themes_branch
        self.ocw_hugo_projects_url = site.starter.ocw_hugo_projects_url
        self.ocw_hugo_projects_branch = ocw_hugo_projects_branch
        if self.is_root_website:
            self.base_url = ""
            self.delete_flag = ""
            self.static_resources_subdirectory = f"/{site.get_url_path()}/"
        else:
            self.base_url = site.get_url_path()
            self.static_resources_subdirectory = "/"
            self.delete_flag = " --delete"
        if self.is_test_website:
            self.noindex = "true"
            self.web_bucket = settings.AWS_TEST_BUCKET_NAME
            self.offline_bucket = settings.AWS_OFFLINE_TEST_BUCKET_NAME
            self.static_api_url = settings.STATIC_API_BASE_URL_TEST or DEV_TEST_URL
            self.resource_base_url = self.static_api_url
            self.sitemap_domain = urlparse(self.static_api_url).netloc
            self.ocw_studio_url = self.static_api_url if self.is_root_website else ""
        starter_slug = site.starter.slug
        base_hugo_args = {"--themesDir": f"../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/"}
        base_online_args = base_hugo_args.copy()
        base_online_args.update(
            {
                "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config.yaml",  # noqa: E501
                "--baseURL": f"/{self.base_url}",
                "--destination": "output-online",
            }
        )
        base_offline_args = base_hugo_args.copy()
        base_offline_args.update(
            {
                "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config-offline.yaml",  # noqa: E501
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
        self.namespace = namespace
        self.vars = get_site_pipeline_definition_vars(namespace=namespace)
        self.values = {
            "is_root_website": 1 if self.is_root_website else 0,
            "short_id": site.short_id,
            "site_name": site.name,
            "s3_path": site.s3_path,
            "url_path": self.url_path,
            "base_url": self.base_url,
            "static_resources_subdirectory": self.static_resources_subdirectory,
            "delete_flag": self.delete_flag,
            "noindex": self.noindex,
            "pipeline_name": pipeline_name,
            "instance_vars": instance_vars,
            "sitemap_domain": self.sitemap_domain,
            "static_api_url": self.static_api_url,
            "storage_bucket": storage_bucket,
            "artifacts_bucket": artifacts_bucket,
            "web_bucket": self.web_bucket,
            "offline_bucket": self.offline_bucket,
            "resource_base_url": self.resource_base_url,
            "site_content_branch": site_content_branch,
            "ocw_hugo_themes_branch": ocw_hugo_themes_branch,
            "ocw_hugo_projects_url": self.ocw_hugo_projects_url,
            "ocw_hugo_projects_branch": ocw_hugo_projects_branch,
            "ocw_studio_url": self.ocw_studio_url,
            "hugo_args_online": hugo_args_online,
            "hugo_args_offline": hugo_args_offline,
            "prefix": f"{prefix.strip('/')}/" if prefix != "" else prefix,
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
            self.extend(
                [OpenCatalogResource(url) for url in settings.OPEN_CATALOG_URLS]
            )


class SitePipelineBaseTasks(list[StepModifierMixin]):
    def __init__(
        self,
        config: SitePipelineDefinitionConfig,
        gated: bool = False,  # noqa: FBT001, FBT002
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
        get_steps = [
            webpack_manifest_get_step,
            ocw_hugo_themes_get_step,
            ocw_hugo_projects_get_step,
            site_content_get_step,
        ]
        if gated:
            for get_step in get_steps:
                get_step.passed = [passed_identifier]
        self.extend(get_steps)


class FilterWebpackArtifactsStep(TaskStep):
    def __init__(self, web_bucket: str):
        super().__init__(
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
                        f"jq -r 'values[]' ./{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json | xargs -I {{}} aws s3{get_cli_endpoint_url()} cp s3://{web_bucket}{{}} ./{WEBPACK_ARTIFACTS_IDENTIFIER}/{{}} --exclude *.js.map",  # noqa: E501
                    ],
                ),
            ),
        )
        if is_dev():
            self.params["AWS_ACCESS_KEY_ID"] = settings.AWS_ACCESS_KEY_ID
            self.params["AWS_SECRET_ACCESS_KEY"] = settings.AWS_SECRET_ACCESS_KEY


class StaticResourcesTaskStep(TaskStep):
    """
    A TaskStep to fetch the static resources for a site from S3

    Args:
        pipeline_vars(dict): A dictionary of site pipeline variables
    """

    def __init__(self, pipeline_vars: dict, *, filter_videos: bool = False):
        video_filter = " --exclude *.mp4" if filter_videos else ""
        super().__init__(
            task=STATIC_RESOURCES_S3_IDENTIFIER,
            timeout="120m",
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
                        f"aws s3{get_cli_endpoint_url()} sync s3://{pipeline_vars['storage_bucket']}/{pipeline_vars['s3_path']} ./{STATIC_RESOURCES_S3_IDENTIFIER}{video_filter}",  # noqa: E501
                    ],
                ),
            ),
        )
        add_error_handling(
            step=self,
            step_description=f"{STATIC_RESOURCES_S3_IDENTIFIER} s3 sync to container",
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
        )
        if is_dev():
            self.params["AWS_ACCESS_KEY_ID"] = settings.AWS_ACCESS_KEY_ID or ""
            self.params["AWS_SECRET_ACCESS_KEY"] = settings.AWS_SECRET_ACCESS_KEY or ""


class SitePipelineOnlineTasks(list[StepModifierMixin]):
    """
    The tasks used in the online site job

    Args:
        pipeline_vars(dict): A dictionary of site pipeline variables
        fastly_var(str): A string to append to fastly_ and form a var name where Fastly connection info is stored
        destructive_sync(bool): (Optional) A boolean override for the delete flag used in AWS syncs
        filter_videos(bool): (Optional) A boolean override for filtering videos out of AWS syncs
        skip_cache_clear(bool): (Optional) A boolean override for skipping the CDN cache clear step
        skip_search_index_update(bool): (Optional) A boolean override for skipping the search index update
    """  # noqa: E501

    def __init__(  # noqa: PLR0913
        self,
        pipeline_vars: dict,
        fastly_var: str,
        *,
        destructive_sync: bool = True,
        filter_videos: bool = False,
        skip_cache_clear: bool = False,
        skip_search_index_update: bool = False,
    ):
        delete_flag = pipeline_vars["delete_flag"] if destructive_sync else ""
        static_resources_task_step = StaticResourcesTaskStep(
            pipeline_vars=pipeline_vars, filter_videos=filter_videos
        )
        build_online_site_step = add_error_handling(
            step=TaskStep(
                task=BUILD_ONLINE_SITE_IDENTIFIER,
                timeout="20m",
                attempts=3,
                params={
                    "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
                    "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
                    "OCW_STUDIO_BASE_URL": pipeline_vars["ocw_studio_url"],
                    "STATIC_API_BASE_URL": pipeline_vars["static_api_url"],
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "RESOURCE_BASE_URL": pipeline_vars["resource_base_url"],
                    "SITEMAP_DOMAIN": pipeline_vars["sitemap_domain"],
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                    "NOINDEX": pipeline_vars["noindex"],
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
                            hugo {pipeline_vars['hugo_args_online']}
                            cp -r -n ../{STATIC_RESOURCES_S3_IDENTIFIER}/. ./output-online{pipeline_vars['static_resources_subdirectory']}
                            """,  # noqa: E501
                        ],
                    ),
                ),
            ),
            step_description=f"{BUILD_ONLINE_SITE_IDENTIFIER} task step",
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
        )
        if is_dev():
            build_online_site_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            build_online_site_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY

        online_sync_command = f"""
        aws configure set default.s3.max_concurrent_requests $AWS_MAX_CONCURRENT_CONNECTIONS
        if [ $IS_ROOT_WEBSITE = 1 ] ; then
            aws s3{get_cli_endpoint_url()} cp {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{pipeline_vars['web_bucket']}/{pipeline_vars['prefix']}{pipeline_vars['base_url']} --recursive --metadata site-id={pipeline_vars['site_name']}{pipeline_vars['delete_flag']}
        else
            aws s3{get_cli_endpoint_url()} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{pipeline_vars['web_bucket']}/{pipeline_vars['prefix']}{pipeline_vars['base_url']} --exclude='{pipeline_vars['short_id']}.zip' --exclude='{pipeline_vars['short_id']}-video.zip' --metadata site-id={pipeline_vars['site_name']}{delete_flag}
        fi
        """  # noqa: E501
        upload_online_build_step = add_error_handling(
            step=TaskStep(
                task=UPLOAD_ONLINE_BUILD_IDENTIFIER,
                timeout="40m",
                params={
                    "AWS_MAX_CONCURRENT_CONNECTIONS": str(
                        settings.AWS_MAX_CONCURRENT_CONNECTIONS
                    ),
                    "IS_ROOT_WEBSITE": pipeline_vars["is_root_website"],
                },
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[Input(name=SITE_CONTENT_GIT_IDENTIFIER)],
                    run=Command(path="sh", args=["-exc", online_sync_command]),
                ),
            ),
            step_description=f"{UPLOAD_ONLINE_BUILD_IDENTIFIER} task step",
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
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
                fastly_var=f"fastly_{fastly_var}",
                site_name=pipeline_vars["site_name"],
            ),
            step_description="clear cdn cache",
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
        )
        clear_cdn_cache_online_on_success_steps = []
        if not skip_search_index_update:
            clear_cdn_cache_online_on_success_steps.extend(
                [
                    *[
                        OpenCatalogWebhookStep(
                            site_url=pipeline_vars["url_path"],
                            pipeline_name=pipeline_vars["pipeline_name"],
                            open_catalog_url=open_catalog_url,
                        )
                        for open_catalog_url in settings.OPEN_CATALOG_URLS
                    ]
                ]
            )
        clear_cdn_cache_online_on_success_steps.append(
            OcwStudioWebhookStep(
                pipeline_name=pipeline_vars["pipeline_name"],
                status="succeeded",
            )
        )
        clear_cdn_cache_online_step.on_success = TryStep(
            try_=DoStep(do=clear_cdn_cache_online_on_success_steps)
        )
        self.extend(
            [
                static_resources_task_step,
                build_online_site_step,
                upload_online_build_step,
            ]
        )
        if not is_dev() and not skip_cache_clear:
            self.append(clear_cdn_cache_online_step)


class SitePipelineOfflineTasks(list[StepModifierMixin]):
    """
    The tasks used in the offline site job

    Args:
        pipeline_vars(dict): A dictionary of site pipeline variables
        fastly_var(str): A string to append to fastly_ and form a var name where Fastly connection info is stored
    """  # noqa: E501

    def __init__(self, pipeline_vars: dict, fastly_var: str):
        static_resources_task_step = StaticResourcesTaskStep(
            pipeline_vars=pipeline_vars
        )
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
        hugo {pipeline_vars['hugo_args_offline']}
        if [ $IS_ROOT_WEBSITE = 0 ] ; then
            cd output-offline
            zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{pipeline_vars['short_id']}.zip ./
            rm -rf ./*
            cd ..
            if [ $MP4_COUNT != 0 ];
            then
                mv ../videos/* ./content/static_resources
            fi
            hugo {pipeline_vars['hugo_args_offline']}
            cd output-offline
            zip -r ../../{BUILD_OFFLINE_SITE_IDENTIFIER}/{pipeline_vars['short_id']}-video.zip ./
        fi
        """  # noqa: E501
        build_offline_site_step = add_error_handling(
            step=TaskStep(
                task=BUILD_OFFLINE_SITE_IDENTIFIER,
                timeout="120m",
                attempts=3,
                params={
                    "API_BEARER_TOKEN": settings.API_BEARER_TOKEN,
                    "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
                    "OCW_STUDIO_BASE_URL": pipeline_vars["ocw_studio_url"],
                    "STATIC_API_BASE_URL": pipeline_vars["static_api_url"],
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "RESOURCE_BASE_URL": pipeline_vars["resource_base_url"] or "",
                    "SITEMAP_DOMAIN": pipeline_vars["sitemap_domain"],
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN,
                    "NOINDEX": pipeline_vars["noindex"],
                    "IS_ROOT_WEBSITE": pipeline_vars["is_root_website"],
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
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
        )
        if is_dev():
            build_offline_site_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            build_offline_site_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        offline_sync_command = f"""
        aws configure set default.s3.max_concurrent_requests $AWS_MAX_CONCURRENT_CONNECTIONS
        if [ $IS_ROOT_WEBSITE = 1 ] ; then
            aws s3{get_cli_endpoint_url()} cp {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{pipeline_vars['offline_bucket']}/{pipeline_vars['prefix']}{pipeline_vars['base_url']} --recursive --metadata site-id={pipeline_vars['site_name']}{pipeline_vars['delete_flag']}
        else
            aws s3{get_cli_endpoint_url()} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{pipeline_vars['offline_bucket']}/{pipeline_vars['prefix']}{pipeline_vars['base_url']} --metadata site-id={pipeline_vars['site_name']}{pipeline_vars['delete_flag']}
        fi
        if [ $IS_ROOT_WEBSITE = 0 ] ; then
            aws s3{get_cli_endpoint_url()} sync {BUILD_OFFLINE_SITE_IDENTIFIER}/ s3://{pipeline_vars['web_bucket']}/{pipeline_vars['prefix']}{pipeline_vars['base_url']} --exclude='*' --include='{pipeline_vars['short_id']}.zip' --include='{pipeline_vars['short_id']}-video.zip' --metadata site-id={pipeline_vars['site_name']}
        fi
        """  # noqa: E501
        upload_offline_build_step = add_error_handling(
            step=TaskStep(
                task=UPLOAD_OFFLINE_BUILD_IDENTIFIER,
                timeout="120m",
                params={
                    "AWS_MAX_CONCURRENT_CONNECTIONS": str(
                        settings.AWS_MAX_CONCURRENT_CONNECTIONS
                    ),
                    "IS_ROOT_WEBSITE": pipeline_vars["is_root_website"],
                },
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
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
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
                fastly_var=f"fastly_{fastly_var}",
                site_name=pipeline_vars["site_name"],
            ),
            step_description="clear cdn cache",
            pipeline_name=pipeline_vars["pipeline_name"],
            short_id=pipeline_vars["short_id"],
            instance_vars=pipeline_vars["instance_vars"],
        )
        clear_cdn_cache_offline_step.on_success = TryStep(
            try_=DoStep(
                do=[
                    *[
                        OpenCatalogWebhookStep(
                            site_url=pipeline_vars["url_path"],
                            pipeline_name=pipeline_vars["pipeline_name"],
                            open_catalog_url=open_catalog_url,
                        )
                        for open_catalog_url in settings.OPEN_CATALOG_URLS
                    ],
                    OcwStudioWebhookStep(
                        pipeline_name=pipeline_vars["pipeline_name"],
                        status="succeeded",
                    ),
                ]
            )
        )
        self.extend(
            [
                static_resources_task_step,
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
                inputs=[],
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
                    "is_root_website": config.values["is_root_website"],
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
                    "sitemap_domain": config.values["sitemap_domain"],
                    "static_api_url": config.values["static_api_url"],
                    "storage_bucket": config.values["storage_bucket"],
                    "artifacts_bucket": config.values["artifacts_bucket"],
                    "web_bucket": config.values["web_bucket"],
                    "offline_bucket": config.values["offline_bucket"],
                    "resource_base_url": config.values["resource_base_url"],
                    "site_content_branch": config.values["site_content_branch"],
                    "ocw_hugo_themes_branch": config.values["ocw_hugo_themes_branch"],
                    "ocw_hugo_projects_url": config.values["ocw_hugo_projects_url"],
                    "ocw_hugo_projects_branch": config.values[
                        "ocw_hugo_projects_branch"
                    ],
                    "ocw_studio_url": config.values["ocw_studio_url"],
                    "hugo_args_online": config.values["hugo_args_online"],
                    "hugo_args_offline": config.values["hugo_args_offline"],
                    "prefix": config.values["prefix"],
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
        ocw_studio_webhook_started_step = OcwStudioWebhookStep(
            pipeline_name=config.vars["pipeline_name"],
            status="started",
        )
        steps = [ocw_studio_webhook_started_step]
        steps.extend(SitePipelineBaseTasks(config=config))
        skip_cache_clear = is_test_site(config.site.name)
        online_tasks = SitePipelineOnlineTasks(
            pipeline_vars=config.vars,
            fastly_var=config.pipeline_name,
            skip_cache_clear=skip_cache_clear,
        )
        for task in online_tasks:
            if hasattr(task, "task") and task.task == UPLOAD_ONLINE_BUILD_IDENTIFIER:
                task.on_success = OcwStudioWebhookStep(
                    pipeline_name=config.vars["pipeline_name"],
                    status="succeeded",
                )
        steps.extend(online_tasks)
        return Job(
            name=self._online_site_job_identifier,
            serial=True,
            plan=steps,
        )

    def get_offline_build_job(self, config: SitePipelineDefinitionConfig):
        steps = []
        steps.extend(
            SitePipelineBaseTasks(
                config=config,
                gated=True,
                passed_identifier=self._online_site_job_identifier,
            )
        )
        steps.append(FilterWebpackArtifactsStep(web_bucket=config.vars["web_bucket"]))
        steps.extend(
            SitePipelineOfflineTasks(
                pipeline_vars=config.vars, fastly_var=config.pipeline_name
            )
        )
        return Job(
            name=self._offline_site_job_identifier,
            serial=True,
            plan=steps,
        )
