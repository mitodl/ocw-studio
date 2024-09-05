import json
from random import shuffle
from typing import Optional
from urllib.parse import quote

import more_itertools
from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    AcrossVar,
    DoStep,
    Duration,
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
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_TRIGGER_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    WEBPACK_MANIFEST_S3_IDENTIFIER,
    WEBPACK_MANIFEST_S3_TRIGGER_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.resource_types import (
    HttpResourceType,
    KeyvalResourceType,
    S3IamResourceType,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    GitResource,
    OcwHugoProjectsGitResource,
    OcwHugoThemesGitResource,
    OcwStudioWebhookResource,
    OpenCatalogResource,
    SlackAlertResource,
    WebpackManifestResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    SiteContentGitTaskStep,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    FilterWebpackArtifactsStep,
    SitePipelineDefinitionConfig,
    SitePipelineOfflineTasks,
    SitePipelineOnlineTasks,
    get_site_pipeline_definition_vars,
)
from content_sync.utils import get_common_pipeline_vars, get_publishable_sites
from main.utils import is_dev
from websites.models import Website, WebsiteStarter


class MassBuildSitesPipelineDefinitionConfig:
    """
    A class with configuration properties for building a mass build pipeline

    Args:
        version(str): The version of the sites to build in the pipeline (draft / live)
        artifacts_bucket(str): The versioned bucket where the webpack manifest is stored (ol-eng-artifacts)
        site_content_branch(str): The branch to use in the site content repo (preview / release)
        ocw_hugo_themes_branch(str): The branch of ocw-hugo-themes to use
        ocw_hugo_projects_branch(str): The branch of ocw-hugo-projects to use
        offline(bool): Determines whether the pipeline will perform the online or offline build of each site
        instance_vars(str): The instance vars for the pipeline in a query string format
        starter(WebsiteStarter): (Optional) Filter the sites to be built by a WebsiteStarter
        prefix(str): (Optional) A prefix path to use when deploying the websites to their destination
        hugo_override_args(str): (Optional) Arguments to override in the hugo command
    """  # noqa: E501

    def __init__(  # noqa: PLR0913
        self,
        version: str,
        artifacts_bucket: str,
        site_content_branch: str,
        ocw_hugo_themes_branch: str,
        ocw_hugo_projects_branch: str,
        offline: bool,  # noqa: FBT001
        instance_vars: str,
        starter: Optional[WebsiteStarter] = None,
        prefix: Optional[str] = "",
        hugo_arg_overrides: Optional[str] = None,
    ):
        vars = get_common_pipeline_vars()  # noqa: A001
        sites = list(get_publishable_sites(version))
        shuffle(sites)
        self.sites = sites
        self.version = version
        self.prefix = prefix
        self.artifacts_bucket = artifacts_bucket
        self.site_content_branch = site_content_branch
        self.ocw_hugo_themes_branch = ocw_hugo_themes_branch
        self.ocw_hugo_projects_branch = ocw_hugo_projects_branch
        self.starter = starter
        self.offline = offline
        self.hugo_arg_overrides = hugo_arg_overrides
        self.instance_vars = instance_vars
        self.web_bucket = (
            vars["preview_bucket_name"]
            if version == VERSION_DRAFT
            else vars["publish_bucket_name"]
        )


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
        site_pipeline_vars = get_site_pipeline_definition_vars(namespace=".:site.")
        webpack_manifest_resource = WebpackManifestResource(
            name=WEBPACK_MANIFEST_S3_IDENTIFIER,
            bucket=config.artifacts_bucket,
            branch=config.ocw_hugo_themes_branch,
        )
        webpack_manifest_trigger_resource = WebpackManifestResource(
            name=WEBPACK_MANIFEST_S3_TRIGGER_IDENTIFIER,
            bucket=config.artifacts_bucket,
            branch=config.ocw_hugo_themes_branch,
        )
        webpack_manifest_trigger_resource.check_every = Duration("1m")
        ocw_hugo_themes_resource = OcwHugoThemesGitResource(
            branch=config.ocw_hugo_themes_branch
        )
        root_starter = Website.objects.get(name=settings.ROOT_WEBSITE_NAME).starter
        ocw_hugo_projects_resource = OcwHugoProjectsGitResource(
            uri=root_starter.ocw_hugo_projects_url,
            branch=config.ocw_hugo_projects_branch,
        )
        ocw_hugo_projects_trigger_resource = GitResource(
            name=OCW_HUGO_PROJECTS_GIT_TRIGGER_IDENTIFIER,
            uri=root_starter.ocw_hugo_projects_url,
            branch=config.ocw_hugo_projects_branch,
        )
        ocw_hugo_projects_trigger_resource.check_every = Duration("1m")
        self.append(webpack_manifest_resource)
        self.append(webpack_manifest_trigger_resource)
        self.append(ocw_hugo_themes_resource)
        self.append(ocw_hugo_projects_resource)
        self.append(ocw_hugo_projects_trigger_resource)
        self.append(
            OcwStudioWebhookResource(
                site_name=site_pipeline_vars["site_name"],
                api_token=settings.API_BEARER_TOKEN or "",
            )
        )
        self.append(SlackAlertResource())
        if not is_dev() and config.version == "live":
            self.extend(
                [OpenCatalogResource(url) for url in settings.OPEN_CATALOG_URLS]
            )


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
    """  # noqa: E501

    def __init__(self, config: MassBuildSitesPipelineDefinitionConfig, **kwargs):
        base = super()
        pipeline_vars = get_common_pipeline_vars()
        namespace = ".:site."
        site_pipeline_vars = get_site_pipeline_definition_vars(namespace)
        resource_types = MassBuildSitesPipelineResourceTypes()
        resources = MassBuildSitesResources(config=config)
        base_tasks = MassBuildSitesPipelineBaseTasks()
        filter_webpack_artifacts_step = FilterWebpackArtifactsStep(
            web_bucket=config.web_bucket
        )
        jobs = []
        batch_gate_resources = []
        batches = list(
            more_itertools.batched(config.sites, settings.OCW_MASS_BUILD_BATCH_SIZE)
        )
        batch_count = len(batches)
        batch_number = 1
        for batch in batches:
            tasks = []
            if batch_number == 1:
                trigger = not config.offline
                tasks.extend(
                    [
                        GetStep(
                            get=WEBPACK_MANIFEST_S3_TRIGGER_IDENTIFIER,
                            trigger=trigger,
                            timeout="5m",
                            attempts=3,
                        ),
                        GetStep(
                            get=OCW_HUGO_PROJECTS_GIT_TRIGGER_IDENTIFIER,
                            trigger=trigger,
                            timeout="5m",
                            attempts=3,
                        ),
                    ]
                )
            if batch_number < batch_count:
                batch_gate_resources.append(
                    Resource(
                        name=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number}",
                        type=KEYVAL_RESOURCE_TYPE_IDENTIFIER,
                        icon="gate",
                        check_every="never",
                    )
                )
            tasks.extend(base_tasks)
            if config.offline:
                tasks.append(filter_webpack_artifacts_step)
            across_var_values = []
            if config.version == VERSION_DRAFT:
                static_api_url = pipeline_vars["static_api_base_url_draft"]
                web_bucket = pipeline_vars["preview_bucket_name"]
                offline_bucket = pipeline_vars["offline_preview_bucket_name"]
                resource_base_url = pipeline_vars["resource_base_url_draft"]
            else:
                static_api_url = pipeline_vars["static_api_base_url_live"]
                web_bucket = pipeline_vars["publish_bucket_name"]
                offline_bucket = pipeline_vars["offline_publish_bucket_name"]
                resource_base_url = pipeline_vars["resource_base_url_live"]
            for site in batch:
                site_config = SitePipelineDefinitionConfig(
                    site=site,
                    pipeline_name=config.version,
                    instance_vars=f"?vars={quote(json.dumps({'site': site.name}))}",
                    site_content_branch=config.site_content_branch,
                    static_api_url=static_api_url,
                    storage_bucket=pipeline_vars["storage_bucket_name"],
                    artifacts_bucket=pipeline_vars["artifacts_bucket_name"],
                    web_bucket=web_bucket,
                    offline_bucket=offline_bucket,
                    resource_base_url=resource_base_url,
                    ocw_hugo_themes_branch=config.ocw_hugo_themes_branch,
                    ocw_hugo_projects_branch=config.ocw_hugo_projects_branch,
                    namespace=namespace,
                    prefix=config.prefix,
                )
                across_var_values.append(site_config.values)

            site_build_tasks = [
                SiteContentGitTaskStep(
                    branch=site_pipeline_vars["site_content_branch"],
                    short_id=site_pipeline_vars["short_id"],
                )
            ]
            if not config.offline:
                site_build_tasks.extend(
                    SitePipelineOnlineTasks(
                        pipeline_vars=site_pipeline_vars,
                        fastly_var=config.version,
                        pipeline_name=config.version,
                        destructive_sync=False,
                        filter_videos=True,
                    )
                )
            else:
                site_build_tasks.extend(
                    SitePipelineOfflineTasks(
                        pipeline_vars=site_pipeline_vars,
                        fastly_var=config.version,
                        pipeline_name=config.version,
                    )
                )
            if batch_number > 1:
                tasks.append(
                    GetStep(
                        get=f"{MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER}-{batch_number -1}",  # noqa: E501
                        passed=[
                            f"{MASS_BUILD_SITES_JOB_IDENTIFIER}-batch-{batch_number - 1}"  # noqa: E501
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
                        inputs=[],
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
