import json
from typing import Optional
from urllib.parse import quote

import more_itertools
from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    AcrossVar,
    DoStep,
    GetStep,
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
    MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER,
    MASS_BUILD_SITES_JOB_IDENTIFIER,
    MASS_BULID_SITES_PIPELINE_IDENTIFIER,
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
    get_site_pipeline_definition_vars,
)
from content_sync.utils import get_template_vars
from websites.models import WebsiteQuerySet, WebsiteStarter


class MassBuildSitesPipelineDefinitionConfig:
    """
    A class with configuration properties for building a mass build pipeline

    Args:
        sites(WebsiteQuerySet): The sites to build the pipeline for
        version(str): The version of the sites to build in the pipeline (draft / live)
        ocw_studio_url(str): The URL to the instance of ocw-studio the pipeline should call home to
        artifacts_bucket(str): The versioned bucket where the webpack manifest is stored (ol-eng-artifacts)
        site_content_branch(str): The branch to use in the site content repo (preview / release)
        ocw_hugo_themes_branch(str): The branch of ocw-hugo-themes to use
        ocw_hugo_projects_branch(str): The branch of ocw-hugo-projects to use
        offline(bool): Determines whether the pipeline will perform the online or offline build of each site
        instance_vars(str): The instance vars for the pipeline in a query string format
        starter(WebsiteStarter): (Optional) Filter the sites to be built by a WebsiteStarter
        prefix(str): (Optional) A prefix path to use when deploying the websites to their destination
        hugo_override_args(str): (Optional) Arguments to override in the hugo command
    """

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
    The ResourceType objects used in the mass build pipeline
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
    """
    The Resource objects used in a mass build pipeline

    Args:
        config(MassBuildSitesPipelineDefinitionConfig): The mass build config object
    """

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
                site_name=MASS_BULID_SITES_PIPELINE_IDENTIFIER,
                api_token=settings.API_BEARER_TOKEN or "",
            )
        )
        self.append(SlackAlertResource())


class MassBuildSitesPipelineBaseTasks(list[StepModifierMixin]):
    """
    The common task objects used in the mass build pipeline
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


class MassBuildSitesPipelineDefinition(Pipeline):
    """
    The Pipeline object representing the mass build

    The sites are separated in batches, configured by settings.OCW_MASS_BUILD_BATCH_SIZE

    Each batch builds sites in parallel, the amount of which is controlled by settings.OCW_MASS_BUILD_MAX_IN_FLIGHT

    Args:
        config(MassBuildSitesPipelineDefinitionConfig): The mass build config object
    """

    def __init__(self, config: MassBuildSitesPipelineDefinitionConfig, **kwargs):
        base = super()
        vars = get_template_vars()
        namespace = ".:site."
        resource_types = MassBuildSitesPipelineResourceTypes()
        resources = MassBuildSitesResources(config=config)
        base_tasks = MassBuildSitesPipelineBaseTasks()
        jobs = []
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
                        name=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number}",
                        type=KEYVAL_RESOURCE_TYPE_IDENTIFIER,
                        icon="gate",
                        check_every="never",
                    )
                )
            tasks = []
            tasks.extend(base_tasks)
            across_var_values = []
            site_pipeline_definition_vars = get_site_pipeline_definition_vars(namespace)
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
                    namespace=namespace,
                )
                across_var_values.append(site_config.values)

            site_build_tasks = [
                SiteContentGitTaskStep(
                    branch=site_pipeline_definition_vars["site_content_branch"],
                    short_id=site_pipeline_definition_vars["short_id"],
                )
            ]
            if not config.offline:
                site_build_tasks.extend(SitePipelineOnlineTasks(config=site_config))
            else:
                site_build_tasks.extend(SitePipelineOfflineTasks(config=site_config))
            if batch_number > 1:
                tasks.append(
                    GetStep(
                        get=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number -1}",
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
                        put=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number}",
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
