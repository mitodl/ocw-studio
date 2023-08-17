import json
from typing import Optional
from urllib.parse import quote

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    DoStep,
    GetStep,
    Identifier,
    InParallelConfig,
    InParallelStep,
    Job,
    Pipeline,
    Resource,
    ResourceType,
    StepModifierMixin,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import VERSION_DRAFT
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
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
    SiteContentGitResource,
    SlackAlertResource,
    WebpackManifestResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import add_error_handling
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    SitePipelineDefinitionConfig,
    SitePipelineOfflineTasks,
    SitePipelineOnlineTasks,
)
from content_sync.utils import get_template_vars
from websites.models import WebsiteQuerySet, WebsiteStarter


MASS_BUILD_SITES_PIPELINE_IDENTIFIER = Identifier("mass-build-sites").root
MASS_BUILD_SITES_JOB_IDENTIFIER = Identifier("mass-build-sites-job").root


class MassBuildSitesPipelineDefinitionConfig:
    def __init__(
        self,
        sites: WebsiteQuerySet,
        version: str,
        ocw_studio_url: str,
        artifacts_bucket: str,
        site_content_branch: str,
        ocw_hugo_themes_branch: str,
        ocw_hugo_projects_branch: str,
        offline: bool,
        instance_vars: str,
        starter: Optional[WebsiteStarter] = None,
        prefix: Optional[str] = None,
        hugo_arg_overrides: Optional[str] = None,
    ):
        self.sites = sites
        self.version = version
        self.prefix = prefix
        self.ocw_studio_url = ocw_studio_url
        self.artifacts_bucket = artifacts_bucket
        self.site_content_branch = site_content_branch
        self.ocw_hugo_themes_branch = ocw_hugo_themes_branch
        self.ocw_hugo_projects_branch = ocw_hugo_projects_branch
        self.starter = starter
        self.offline = offline
        self.hugo_arg_overrides = hugo_arg_overrides
        self.instance_vars = instance_vars
        self.webpack_manifest_s3_identifier = Identifier(
            f"{WEBPACK_MANIFEST_S3_IDENTIFIER}-{ocw_hugo_themes_branch}"
        ).root


class MassBuildSitesPipelineResourceTypes(list[ResourceType]):
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


class MassBuildSitesResources(list[Resource]):
    def __init__(self, config: MassBuildSitesPipelineDefinitionConfig):
        webpack_manifest_resource = WebpackManifestResource(
            name=config.webpack_manifest_s3_identifier,
            bucket=config.artifacts_bucket,
            branch=config.ocw_hugo_themes_branch,
        )
        ocw_hugo_themes_resource = OcwHugoThemesGitResource(
            branch=config.ocw_hugo_themes_branch
        )
        root_starter = WebsiteStarter.objects.get(slug=settings.ROOT_WEBSITE_NAME)
        ocw_hugo_projects_resource = OcwHugoProjectsGitResource(
            uri=root_starter.ocw_hugo_projects_url,
            branch=config.ocw_hugo_projects_branch,
        )
        site_content_resources = []
        ocw_studio_webhook_resources = []
        for site in config.sites:
            site_content_resources.append(
                SiteContentGitResource(
                    name=f"{SITE_CONTENT_GIT_IDENTIFIER}-{site.short_id.lower()}",
                    branch=config.site_content_branch,
                    short_id=site.short_id.lower(),
                )
            )
            ocw_studio_webhook_resources.append(
                OcwStudioWebhookResource(
                    ocw_studio_url=config.ocw_studio_url,
                    site_name=site.name,
                    short_id=site.short_id.lower(),
                    api_token=settings.API_BEARER_TOKEN or "",
                )
            )
        self.append(webpack_manifest_resource)
        self.append(ocw_hugo_themes_resource)
        self.append(ocw_hugo_projects_resource)
        self.extend(site_content_resources)
        self.extend(ocw_studio_webhook_resources)
        self.append(SlackAlertResource())


class MassBuildSitesPipelineBaseTasks(list[StepModifierMixin]):
    def __init__(self, config: MassBuildSitesPipelineDefinitionConfig, **kwargs):
        webpack_manifest_get_step = GetStep(
            get=config.webpack_manifest_s3_identifier,
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


class MassBuildSitesPipelineDefinition(Pipeline):
    def __init__(self, config: MassBuildSitesPipelineDefinitionConfig, **kwargs):
        base = super()
        resource_types = MassBuildSitesPipelineResourceTypes()
        resources = MassBuildSitesResources(config=config)
        tasks = []
        tasks.extend(MassBuildSitesPipelineBaseTasks(config=config))
        site_build_steps = []
        for site in config.sites:
            vars = get_template_vars()
            site_config = SitePipelineDefinitionConfig(
                site=site,
                pipeline_name=config.version,
                instance_vars=f"?vars={quote(json.dumps({'site': site.name}))}",
                site_content_branch=config.site_content_branch,
                static_api_url=settings.STATIC_API_BASE_URL,
                storage_bucket=vars["storage_bucket_name"],
                artifacts_bucket=vars["artifacts_bucket_name"],
                web_bucket=vars["preview_bucket_name"]
                if config.version == VERSION_DRAFT
                else vars["publish_bucket_name"],
                offline_bucket=vars["offline_preview_bucket_name"]
                if config.version == VERSION_DRAFT
                else vars["offline_publish_bucket_name"],
                resource_base_url=vars["resource_base_url_draft"]
                if config.version == VERSION_DRAFT
                else vars["resource_base_url_live"],
                ocw_studio_url=vars["ocw_studio_url"],
                ocw_hugo_themes_branch=config.ocw_hugo_themes_branch,
                ocw_hugo_projects_branch=config.ocw_hugo_projects_branch,
            )
            if not config.offline:
                site_build_tasks = SitePipelineOnlineTasks(config=site_config)
            else:
                site_build_tasks = SitePipelineOfflineTasks(config=site_config)
            site_build_steps.append(DoStep(do=site_build_tasks))
        tasks.append(
            InParallelStep(
                in_parallel=InParallelConfig(limit=10, steps=site_build_steps)
            )
        )
        base.__init__(
            resource_types=resource_types,
            resources=resources,
            jobs=[
                Job(
                    name=MASS_BUILD_SITES_JOB_IDENTIFIER,
                    plan=tasks,
                )
            ],
            **kwargs,
        )
