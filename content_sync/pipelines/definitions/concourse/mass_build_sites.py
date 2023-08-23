import json
from typing import Optional
from urllib.parse import quote

import more_itertools
from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    AcrossVar,
    DoStep,
    GetStep,
    Identifier,
    Job,
    Pipeline,
    PutStep,
    Resource,
    ResourceType,
    StepModifierMixin,
)
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import VERSION_DRAFT
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
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
    SlackAlertResource,
    WebpackManifestResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    SiteContentGitTaskStep,
)
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


class MassBuildSitesPipelineResourceTypes(list[ResourceType]):
    """
    The ResourceType objects used in a site pipeline
    """

    def __init__(self):
        self.extend(
            [
                HttpResourceType(),
                KeyvalResourceType(),
                S3IamResourceType(),
                slack_notification_resource(),
            ]
        )


class MassBuildSitesResources(list[Resource]):
    def __init__(self, config: MassBuildSitesPipelineDefinitionConfig):
        webpack_manifest_resource = WebpackManifestResource(
            name=WEBPACK_MANIFEST_S3_IDENTIFIER,
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
        self.append(webpack_manifest_resource)
        self.append(ocw_hugo_themes_resource)
        self.append(ocw_hugo_projects_resource)
        self.append(
            OcwStudioWebhookResource(
                ocw_studio_url=config.ocw_studio_url,
                site_name="mass-build-sites",
                api_token=settings.API_BEARER_TOKEN or "",
            )
        )
        self.append(SlackAlertResource())


class MassBuildSitesPipelineBaseTasks(list[StepModifierMixin]):
    def __init__(self, **kwargs):
        webpack_manifest_get_step = GetStep(
            get=WEBPACK_MANIFEST_S3_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            **kwargs,
        )
        ocw_hugo_themes_get_step = GetStep(
            get=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            **kwargs,
        )
        ocw_hugo_projects_get_step = GetStep(
            get=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            trigger=False,
            timeout="5m",
            attempts=3,
            **kwargs,
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
        vars = get_template_vars()
        resource_types = MassBuildSitesPipelineResourceTypes()
        resources = MassBuildSitesResources(config=config)
        base_tasks = MassBuildSitesPipelineBaseTasks(config=config)
        jobs = []
        batch_gate_identifier = Identifier("batch-gate").root
        batch_gate_resources = []
        batches = list(
            more_itertools.batched(config.sites, settings.OCW_MASS_BUILD_BATCH_SIZE)
        )
        batch_count = len(batches)
        batch_number = 1
        for batch in batches:
            if batch_number < batch_count:
                batch_gate_resources.append(
                    Resource(
                        name=f"{batch_gate_identifier}-{batch_number}",
                        type=KEYVAL_RESOURCE_TYPE_IDENTIFIER,
                        icon="gate",
                        check_every="never",
                    )
                )
            tasks = []
            tasks.extend(base_tasks)
            across_var_values = []
            for site in batch:
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
                    namespace=".:site.",
                )
                across_var_values.append(site_config.values)

            site_build_tasks = [
                SiteContentGitTaskStep(
                    branch=site_config.site_content_branch,
                    short_id=site_config.site.short_id,
                )
            ]
            if not config.offline:
                site_build_tasks.extend(SitePipelineOnlineTasks(config=site_config))
            else:
                site_build_tasks.extend(SitePipelineOfflineTasks(config=site_config))
            if batch_number > 1:
                tasks.append(
                    GetStep(
                        get=f"{batch_gate_identifier}-{batch_number -1}",
                        passed=[
                            f"{MASS_BUILD_SITES_JOB_IDENTIFIER}-batch-{batch_number - 1}"
                        ],
                        trigger=True,
                    )
                )
            tasks.append(
                DoStep(
                    do=site_build_tasks,
                    across=[
                        AcrossVar(
                            var="site",
                            values=across_var_values,
                            max_in_flight=settings.OCW_MASS_BUILD_MAX_IN_FLIGHT,
                        )
                    ],
                )
            )
            if batch_number < batch_count:
                tasks.append(
                    PutStep(
                        put=f"{batch_gate_identifier}-{batch_number}",
                        params={"mapping": "timestamp = now()"},
                    )
                )
            jobs.append(
                Job(
                    name=f"{MASS_BUILD_SITES_JOB_IDENTIFIER}-batch-{batch_number}",
                    plan=tasks,
                )
            )
            batch_number += 1
        resources.extend(batch_gate_resources)
        base.__init__(
            resource_types=resource_types,
            resources=resources,
            jobs=jobs,
            **kwargs,
        )
