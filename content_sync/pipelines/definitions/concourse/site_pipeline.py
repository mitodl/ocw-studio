from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    DoStep,
    Identifier,
    Input,
    Job,
    Output,
    Pipeline,
    Resource,
    ResourceType,
    TaskConfig,
    TryStep,
)
from ol_concourse.lib.resource_types import slack_notification_resource
from pydantic import Field

from content_sync.constants import DEV_ENDPOINT_URL
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
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
    GitResource,
    OcwStudioWebhookResource,
    OpenDiscussionsResource,
    SlackAlertResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    GetStepWithErrorHandling,
    OcwStudioWebhookStep,
    OpenDiscussionsWebhookStep,
    PutStepWithErrorHandling,
    TaskStepWithErrorHandling,
)
from main.utils import is_dev
from websites.constants import OCW_HUGO_THEMES_GIT
from websites.models import Website


class SitePipelineDefinitionConfig:
    def __init__(
        self,
        site: Website,
        pipeline_name: str,
        is_root_website: bool,
        base_url: str,
        site_content_branch: str,
        static_api_url: str,
        storage_bucket_name: str,
        artifacts_bucket: str,
        web_bucket: str,
        offline_bucket: str,
        resource_base_url: str,
        static_resources_subdirectory: str,
        noindex: str,
        ocw_studio_url: str,
        ocw_hugo_themes_branch: str,
        ocw_hugo_projects_url: str,
        ocw_hugo_projects_branch: str,
        hugo_args_online: str,
        hugo_args_offline: str,
        delete_flag: str,
        instance_vars: str,
    ):
        self.site = site
        self.pipeline_name = pipeline_name
        self.is_root_website = is_root_website
        self.purge_url = f"purge/{site.name}"
        self.base_url = base_url
        self.site_content_branch = site_content_branch
        self.pipeline_name = pipeline_name
        self.static_api_url = static_api_url
        self.storage_bucket_name = storage_bucket_name
        self.artifacts_bucket = artifacts_bucket
        self.web_bucket = web_bucket
        self.offline_bucket = offline_bucket
        self.resource_base_url = resource_base_url
        self.static_resources_subdirectory = static_resources_subdirectory
        self.noindex = noindex
        self.ocw_studio_url = ocw_studio_url
        self.ocw_hugo_themes_branch = ocw_hugo_themes_branch
        self.ocw_hugo_projects_url = ocw_hugo_projects_url
        self.ocw_hugo_projects_branch = ocw_hugo_projects_branch
        self.hugo_args_online = hugo_args_online
        self.hugo_args_offline = hugo_args_offline
        self.delete_flag = delete_flag
        self.instance_vars = instance_vars
        self.cli_endpoint_url = (
            f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""
        )


class SitePipelineResourceTypes(list[ResourceType]):
    def __init__(self):
        self.extend(
            [
                HttpResourceType(),
                S3IamResourceType(),
                slack_notification_resource(),
            ]
        )


class SitePipelineResources(list[Resource]):
    def __init__(self, config: SitePipelineDefinitionConfig):
        webpack_manifest_resource = Resource(
            name=WEBPACK_MANIFEST_S3_IDENTIFIER,
            type=S3_IAM_RESOURCE_TYPE_IDENTIFIER,
            check_every="never",
            source={
                "bucket": (config.artifacts_bucket or ""),
                "versioned_file": f"ocw-hugo-themes/{config.ocw_hugo_themes_branch}/webpack.json",
            },
        )
        if is_dev():
            webpack_manifest_resource.source.update(
                {
                    "endpoint": DEV_ENDPOINT_URL,
                    "access_key_id": (settings.AWS_ACCESS_KEY_ID or ""),
                    "secret_access_key": (settings.AWS_SECRET_ACCESS_KEY or ""),
                }
            )
        ocw_hugo_themes_resource = GitResource(
            name=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            uri=OCW_HUGO_THEMES_GIT,
            branch=config.ocw_hugo_themes_branch,
        )
        ocw_hugo_projects_resource = GitResource(
            name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            uri=config.ocw_hugo_projects_url,
            branch=config.ocw_hugo_projects_branch,
        )
        site_content_resource_source = {"branch": config.site_content_branch}
        if settings.CONCOURSE_IS_PRIVATE_REPO:
            site_content_resource_source[
                "uri"
            ] = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{config.site.short_id}.git"
            site_content_resource_source["private_key"] = "((git-private-key))"
        else:
            site_content_resource_source[
                "uri"
            ] = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{config.site.short_id}.git"
        site_content_resource = Resource(
            name=SITE_CONTENT_GIT_IDENTIFIER,
            type="git",
            check_every="never",
            source=site_content_resource_source,
        )
        ocw_studio_webhook_resource = OcwStudioWebhookResource(
            ocw_studio_url=config.ocw_studio_url,
            site_name=config.site.name,
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


class SitePipelineDefinition(Pipeline):
    _offline_build_gate_identifier = Identifier("offline-build-gate")
    _online_site_job_identifier = Identifier("online-site-job")
    _build_online_site_identifier = Identifier("build-online-site")
    _upload_online_build_identifier = Identifier("upload-online-build")
    _filter_webpack_artifacts_identifier = Identifier("filter-webpack-artifacts")
    _offline_site_job_identifier = Identifier("offline-site-job")
    _build_offline_site_identifier = Identifier("build-offline-site")
    _upload_offline_build_identifier = Identifier("upload-offline-build")
    _clear_cdn_cache_identifier = Identifier("clear-cdn-cache")

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
            check_every="never",
        )
        resources.append(offline_build_gate_resource)
        online_job = self.get_online_build_job(config=config)
        offline_build_gate_put_step = PutStepWithErrorHandling(
            put=self._offline_build_gate_identifier,
            params={"mapping": "timestamp = now()"},
            step_description=f"{self._offline_build_gate_identifier} task step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        online_job.plan.append(offline_build_gate_put_step)
        offline_job = self.get_offline_build_job(config=config)
        offline_build_gate_get_step = GetStepWithErrorHandling(
            get=self._offline_build_gate_identifier,
            passed=[self._online_site_job_identifier],
            trigger=True,
            step_description=f"{self._offline_build_gate_identifier} get step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        offline_job.plan.insert(0, offline_build_gate_get_step)
        base.__init__(
            resource_types=resource_types,
            resources=resources,
            jobs=[online_job, offline_job],
            **kwargs,
        )

    def get_base_tasks(self, config: SitePipelineDefinitionConfig, offline: bool):
        webpack_manifest_get_step = GetStepWithErrorHandling(
            get=WEBPACK_MANIFEST_S3_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            step_description=f"{WEBPACK_MANIFEST_S3_IDENTIFIER} get step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        ocw_hugo_themes_get_step = GetStepWithErrorHandling(
            get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            step_description=f"{OCW_HUGO_THEMES_GIT_IDENTIFIER} get step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        ocw_hugo_projects_get_step = GetStepWithErrorHandling(
            get=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            step_description=f"{OCW_HUGO_PROJECTS_GIT_IDENTIFIER} get step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        site_content_get_step = GetStepWithErrorHandling(
            get=SITE_CONTENT_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            step_description=f"{SITE_CONTENT_GIT_IDENTIFIER} get step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        static_resources_step = TaskStepWithErrorHandling(
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
                        f"aws s3{config.cli_endpoint_url} sync s3://{config.storage_bucket_name}/{config.site.s3_path} ./{STATIC_RESOURCES_S3_IDENTIFIER}",
                    ],
                ),
            ),
            step_description=f"{STATIC_RESOURCES_S3_IDENTIFIER} s3 sync to container",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        if is_dev():
            static_resources_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            static_resources_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        tasks = []
        get_steps = [
            webpack_manifest_get_step,
            ocw_hugo_themes_get_step,
            ocw_hugo_projects_get_step,
            site_content_get_step,
        ]
        if offline:
            for get_step in get_steps:
                get_step.passed = [self._online_site_job_identifier]
        tasks.extend(get_steps)
        tasks.append(static_resources_step)
        return tasks

    def get_online_tasks(self, config: SitePipelineDefinitionConfig):
        base_tasks = self.get_base_tasks(config=config, offline=False)
        ocw_studio_webhook_started_step = OcwStudioWebhookStep(
            pipeline_name=config.pipeline_name, status="started"
        )
        build_online_site_step = TaskStepWithErrorHandling(
            task=self._build_online_site_identifier,
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
                        hugo {config.hugo_args_online}
                        cp -r -n ../{STATIC_RESOURCES_S3_IDENTIFIER}/. ./output-online{config.static_resources_subdirectory}
                        rm -rf ./output-online{config.static_resources_subdirectory}*.mp4
                        """,
                    ],
                ),
            ),
            step_description=f"{self._build_online_site_identifier} task step",
            pipeline_name=config.pipeline_name,
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
            online_sync_command = f"aws s3{config.cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{config.web_bucket}/{config.base_url} --metadata site-id={config.site.name}{config.delete_flag}"
        else:
            online_sync_command = f"aws s3{config.cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-online s3://{config.web_bucket}/{config.base_url} --exclude='{config.site.short_id}.zip' --exclude='{config.site.short_id}-video.zip' --metadata site-id={config.site.name}{config.delete_flag}"
        upload_online_build_step = TaskStepWithErrorHandling(
            task=self._upload_online_build_identifier,
            timeout="40m",
            params={},
            config=TaskConfig(
                platform="linux",
                image_resource=AWS_CLI_REGISTRY_IMAGE,
                inputs=[Input(name=SITE_CONTENT_GIT_IDENTIFIER)],
                run=Command(path="sh", args=["-exc", online_sync_command]),
            ),
            step_description=f"{self._upload_online_build_identifier} task step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
            on_success=OcwStudioWebhookStep(
                pipeline_name=config.pipeline_name, status="succeeded"
            ),
        )
        if is_dev():
            upload_online_build_step.params["AWS_ACCESS_KEY_ID"] = (
                settings.AWS_ACCESS_KEY_ID or ""
            )
            upload_online_build_step.params["AWS_SECRET_ACCESS_KEY"] = (
                settings.AWS_SECRET_ACCESS_KEY or ""
            )
        clear_cdn_cache_online_step = ClearCdnCacheStep(
            name=self._clear_cdn_cache_identifier,
            fastly_var="fastly",
            purge_url=config.purge_url,
            step_description="clear cdn cache",
            pipeline_name=config.pipeline_name,
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
                        pipeline_name=config.pipeline_name, status="succeeded"
                    ),
                ]
            )
        )
        online_tasks = [ocw_studio_webhook_started_step]
        online_tasks.extend(base_tasks)
        online_tasks.extend([build_online_site_step, upload_online_build_step])
        if not is_dev():
            online_tasks.append(clear_cdn_cache_online_step)
        return online_tasks

    def get_offline_tasks(self, config: SitePipelineDefinitionConfig):
        base_tasks = self.get_base_tasks(config=config, offline=True)
        filter_webpack_artifacts_step = TaskStepWithErrorHandling(
            task=self._filter_webpack_artifacts_identifier,
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
                        f"jq 'recurse | select(type==\"string\")' ./{WEBPACK_MANIFEST_S3_IDENTIFIER}/webpack.json | tr -d '\"' | xargs -I {{}} aws s3{config.cli_endpoint_url} cp s3://{config.web_bucket}{{}} ./{WEBPACK_ARTIFACTS_IDENTIFIER}/{{}} --exclude *.js.map",
                    ],
                ),
            ),
            step_description=f"{self._filter_webpack_artifacts_identifier} task step",
            pipeline_name=config.pipeline_name,
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
        hugo {config.hugo_args_offline}
        """
        if not config.is_root_website:
            build_offline_site_command = f"""
            {build_offline_site_command}
            cd output-offline
            zip -r ../../{self._build_offline_site_identifier}/{config.site.short_id}.zip ./
            rm -rf ./*
            cd ..
            if [ $MP4_COUNT != 0 ];
            then
                mv ../videos/* ./content/static_resources
            fi
            hugo {config.hugo_args_offline}
            cd output-offline
            zip -r ../../{self._build_offline_site_identifier}/{config.site.short_id}-video.zip ./
            """
        build_offline_site_step = TaskStepWithErrorHandling(
            task=self._build_offline_site_identifier,
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
                    Input(name=SITE_CONTENT_GIT_IDENTIFIER),
                    Input(name=STATIC_RESOURCES_S3_IDENTIFIER),
                    Input(name=WEBPACK_MANIFEST_S3_IDENTIFIER),
                    Input(name=WEBPACK_ARTIFACTS_IDENTIFIER),
                ],
                outputs=[
                    Output(name=SITE_CONTENT_GIT_IDENTIFIER),
                    Output(name=OCW_HUGO_THEMES_GIT_IDENTIFIER),
                    Output(name=self._build_offline_site_identifier),
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
            step_description=f"{self._build_offline_site_identifier} task step",
            pipeline_name=config.pipeline_name,
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
            f"aws s3{config.cli_endpoint_url} sync {SITE_CONTENT_GIT_IDENTIFIER}/output-offline/ s3://{config.offline_bucket}/{config.base_url} --metadata site-id={config.site.name}{config.delete_flag}"
        ]
        if not config.is_root_website:
            offline_sync_commands.append(
                f"aws s3{config.cli_endpoint_url} sync {self._build_offline_site_identifier}/ s3://{config.web_bucket}/{config.base_url} --exclude='*' --include='{config.site.short_id}.zip' --include='{config.site.short_id}-video.zip' --metadata site-id={config.site.name}"
            )
        offline_sync_command = "\n".join(offline_sync_commands)
        upload_offline_build_step = TaskStepWithErrorHandling(
            task=self._upload_offline_build_identifier,
            timeout="40m",
            params={},
            config=TaskConfig(
                platform="linux",
                image_resource=AWS_CLI_REGISTRY_IMAGE,
                inputs=[
                    Input(name=SITE_CONTENT_GIT_IDENTIFIER),
                    Input(name=self._build_offline_site_identifier),
                    Input(name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER),
                ],
                run=Command(path="sh", args=["-exc", offline_sync_command]),
            ),
            step_description=f"{self._upload_offline_build_identifier} task step",
            pipeline_name=config.pipeline_name,
            instance_vars=config.instance_vars,
        )
        if is_dev():
            upload_offline_build_step.params[
                "AWS_ACCESS_KEY_ID"
            ] = settings.AWS_ACCESS_KEY_ID
            upload_offline_build_step.params[
                "AWS_SECRET_ACCESS_KEY"
            ] = settings.AWS_SECRET_ACCESS_KEY
        clear_cdn_cache_offline_step = ClearCdnCacheStep(
            name=self._clear_cdn_cache_identifier,
            fastly_var="fastly",
            purge_url=config.purge_url,
            step_description="clear cdn cache",
            pipeline_name=config.pipeline_name,
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
                        pipeline_name=config.pipeline_name, status="succeeded"
                    ),
                ]
            )
        )
        offline_tasks = []
        offline_tasks.extend(base_tasks)
        offline_tasks.extend(
            [
                filter_webpack_artifacts_step,
                build_offline_site_step,
                upload_offline_build_step,
            ]
        )
        if not is_dev():
            offline_tasks.append(clear_cdn_cache_offline_step)
        return offline_tasks

    def get_online_build_job(self, config: SitePipelineDefinitionConfig):
        return Job(
            name=self._online_site_job_identifier,
            serial=True,
            plan=self.get_online_tasks(config=config),
        )

    def get_offline_build_job(self, config: SitePipelineDefinitionConfig):
        return Job(
            name=self._offline_site_job_identifier,
            serial=True,
            plan=self.get_offline_tasks(config=config),
        )
