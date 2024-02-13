"""
Concourse-CI preview/publish pipeline generator
The pylint no-name-in-module is disabled here because of a weird issue
that occurred after adding the OCW_HUGO_THEMES_GIT constant, which
clearly exists but pylint thinks it doesn't
"""
# pylint: disable=no-name-in-module
import json
import logging
import os
from html import unescape
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml
from concoursepy.api import Api
from django.conf import settings
from requests import HTTPError

from content_sync.constants import (
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.decorators import retry_on_failure
from content_sync.pipelines.base import (
    BaseGeneralPipeline,
    BaseMassBuildSitesPipeline,
    BasePipelineApi,
    BaseSitePipeline,
    BaseTestPipeline,
    BaseThemeAssetsPipeline,
    BaseUnpublishedSiteRemovalPipeline,
)
from content_sync.pipelines.definitions.concourse.e2e_test_site_pipeline import (
    EndToEndTestPipelineDefinition,
)
from content_sync.pipelines.definitions.concourse.mass_build_sites import (
    MassBuildSitesPipelineDefinition,
    MassBuildSitesPipelineDefinitionConfig,
)
from content_sync.pipelines.definitions.concourse.remove_unpublished_sites import (
    UnpublishedSiteRemovalPipelineDefinition,
)
from content_sync.pipelines.definitions.concourse.site_pipeline import (
    SitePipelineDefinition,
    SitePipelineDefinitionConfig,
)
from content_sync.pipelines.definitions.concourse.theme_assets_pipeline import (
    ThemeAssetsPipelineDefinition,
)
from content_sync.utils import (
    check_mandatory_settings,
    get_common_pipeline_vars,
    get_projects_branch,
    get_site_content_branch,
    get_theme_branch,
    strip_dev_lines,
    strip_non_dev_lines,
    strip_offline_lines,
    strip_online_lines,
)
from main.utils import is_dev
from websites.constants import STARTER_SOURCE_GITHUB
from websites.models import Website

log = logging.getLogger(__name__)

MANDATORY_CONCOURSE_SETTINGS = [
    "CONCOURSE_URL",
    "CONCOURSE_USERNAME",
    "CONCOURSE_PASSWORD",
]


class PipelineApi(Api, BasePipelineApi):
    """
    Customized pipeline_name of concoursepy.api.Api that allows for getting/setting headers
    """  # noqa: E501

    def __init__(self, url=None, username=None, password=None, token=None):
        """Initialize the API"""
        super().__init__(
            url or settings.CONCOURSE_URL,
            username=username or settings.CONCOURSE_USERNAME,
            password=password or settings.CONCOURSE_PASSWORD,
            token=token or settings.CONCOURSE_TEAM,
        )

    @retry_on_failure
    def auth(self):
        """Same as the base class but with retries and support for concourse 7.7"""  # noqa: D401, E501
        if self.has_username_and_passwd:
            self.ATC_AUTH = None
            session = self._set_new_session()
            # Get initial sky/login response
            r = session.get(urljoin(self.url, "/sky/login"))
            if r.status_code == 200:  # noqa: PLR2004
                # Get second sky/login response based on the url found in the first response  # noqa: E501
                r = session.get(
                    unescape(urljoin(self.url, self._get_login_post_path(r.text)))
                )
                # Post to the final url to authenticate
                post_path = unescape(self._get_login_post_path(r.text))
                r = session.post(
                    urljoin(self.url, post_path),
                    data={"login": self.username, "password": self.password},
                )
                try:
                    r.raise_for_status()
                except HTTPError:
                    self._close_session()
                    raise
                else:
                    # This case does not raise any HTTPError, the return code is 200
                    if "invalid username and password" in r.text:
                        msg = "Invalid username and password"
                        raise ValueError(msg)
                    if r.status_code == requests.codes.ok:
                        self.ATC_AUTH = self._get_skymarshal_auth()
                    else:
                        self._close_session()
        if self.ATC_AUTH:
            return True
        return False

    @retry_on_failure
    def get_with_headers(  # pylint:disable=too-many-branches
        self,
        path: str,
        stream: bool = False,  # noqa: FBT001, FBT002
        iterator: bool = False,  # noqa: FBT001, FBT002
    ) -> tuple[dict, dict]:
        """Customized base get method, returning response data and headers"""  # noqa: D401, E501
        url = self._make_api_url(path)
        r = self.requests.get(url, headers=self.headers, stream=stream)
        if not self._is_response_ok(r) and self.has_username_and_passwd:
            self.auth()
            r = self.requests.get(url, headers=self.headers, stream=stream)
        if r.status_code == requests.codes.ok:
            if stream:
                if iterator:
                    response_data = self.iter_sse_stream(r)
                else:
                    response_data = list(self.iter_sse_stream(r))
            else:
                response_data = json.loads(r.text)
            return response_data, r.headers
        else:
            r.raise_for_status()
            return None

    @retry_on_failure
    def put_with_headers(
        self, path: str, data: dict | None = None, headers: dict | None = None
    ) -> bool:
        """
        Allow additional headers to be sent with a put request
        """
        url = self._make_api_url(path)
        request_headers = self.headers
        request_headers.update(headers or {})
        kwargs = {"headers": request_headers}
        if data is not None:
            kwargs["data"] = data
        r = self.requests.put(url, **kwargs)
        if not self._is_response_ok(r) and self.has_username_and_passwd:
            self.auth()
            r = self.requests.put(url, **kwargs)
        if r.status_code == requests.codes.ok:
            return True
        else:
            r.raise_for_status()
        return False

    @retry_on_failure
    def post(self, path, data=None):
        """Same as base post method but with a retry"""  # noqa: D401
        return super().post(path, data)

    @retry_on_failure
    def put(self, path, data=None):
        """Same as base put method but with a retry"""  # noqa: D401
        return super().put(path, data)

    @retry_on_failure
    def delete(self, path, data=None):
        """Make a delete request"""
        url = self._make_api_url(path)
        kwargs = {"headers": self.headers}
        if data is not None:
            kwargs["data"] = data
        r = self.requests.delete(url, **kwargs)
        if not self._is_response_ok(r) and self.has_username_and_passwd:
            self.auth()
            r = self.requests.delete(url, **kwargs)
        if r.status_code == requests.codes.ok:
            return True
        else:
            r.raise_for_status()
        return False

    def get_pipelines(self, names: list[str] | None = None):
        """Retrieve a list of concourse pipelines, filtered by team and optionally name"""  # noqa: E501
        pipelines = super().list_pipelines(settings.CONCOURSE_TEAM)
        if names:
            pipelines = [
                pipeline for pipeline in pipelines if pipeline["name"] in names
            ]
        return pipelines

    def delete_pipelines(self, names: list[str] | None = None):
        """Delete all pipelines matching filters"""
        pipeline_list = self.get_pipelines(names)
        for item in pipeline_list:
            pipeline = GeneralPipeline(api=self)
            instance_vars = item.get("instance_vars")
            if instance_vars:
                pipeline.set_instance_vars(instance_vars)
            pipeline.delete_pipeline(item["name"])


class GeneralPipeline(BaseGeneralPipeline):
    """Base class for a Concourse pipeline"""

    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS
    PIPELINE_NAME = None

    def __init__(
        self, *args, api: Optional[object] = None, **kwargs  # noqa: ARG002
    ):  # pylint:disable=unused-argument
        """Initialize the pipeline API instance"""
        if self.MANDATORY_SETTINGS:
            check_mandatory_settings(self.MANDATORY_SETTINGS)
        self.instance_vars = ""
        self.api = api or self.get_api()

    @staticmethod
    def get_api():
        """Get a Concourse API instance"""
        return PipelineApi()

    def get_pipeline_definition(
        self, pipeline_file: str, offline: Optional[bool] = None
    ):
        """Get the pipeline definition as a string, processing for environment"""
        with open(  # noqa: PTH123
            os.path.join(  # noqa: PTH118
                os.path.dirname(__file__), pipeline_file  # noqa: PTH120
            )  # noqa: PTH118, PTH120, RUF100
        ) as pipeline_config_file:
            pipeline_config = pipeline_config_file.read()
            pipeline_config = (
                strip_non_dev_lines(pipeline_config)
                if is_dev()
                else strip_dev_lines(pipeline_config)
            )
            return (
                strip_online_lines(pipeline_config)
                if offline
                else strip_offline_lines(pipeline_config)
            )

    def set_instance_vars(self, instance_vars: dict):
        """Set the instance vars for the pipeline"""
        self.instance_vars = f"?vars={quote(json.dumps(instance_vars))}"

    def _make_pipeline_url(self, pipeline_name: str):
        """Make URL for getting/destroying a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}{self.instance_vars}"  # noqa: E501

    def _make_builds_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching builds information"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}/builds{self.instance_vars}"  # noqa: E501

    def _make_pipeline_config_url(self, pipeline_name: str):
        """Make URL for fetching pipeline info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/config{self.instance_vars}"  # noqa: E501

    def _make_job_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching job info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}{self.instance_vars}"  # noqa: E501

    def _make_pipeline_pause_url(self, pipeline_name: str):
        """Make URL for pausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/pause{self.instance_vars}"  # noqa: E501

    def _make_pipeline_unpause_url(self, pipeline_name: str):
        """Make URL for unpausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/unpause{self.instance_vars}"  # noqa: E501

    def trigger_pipeline_build(self, pipeline_name: str) -> int:
        """Trigger a pipeline build"""
        pipeline_info = self.api.get(self._make_pipeline_config_url(pipeline_name))
        job_name = pipeline_info["config"]["jobs"][0]["name"]
        return self.api.post(self._make_builds_url(pipeline_name, job_name))["id"]

    def pause_pipeline(self, pipeline_name: str):
        """Pause the pipeline"""
        self.api.put(self._make_pipeline_pause_url(pipeline_name))

    def unpause_pipeline(self, pipeline_name: str):
        """Unpause the pipeline"""
        self.api.put(self._make_pipeline_unpause_url(pipeline_name))

    def delete_pipeline(self, pipeline_name: str):
        """Delete a pipeline"""
        self.api.delete(self._make_pipeline_url(pipeline_name))

    def get_build_status(self, build_id: int):
        """Retrieve the status of the build"""
        return self.api.get_build(build_id)["status"]

    def abort_build(self, build_id: int):
        """Abort a build"""
        return self.api.abort_build(build_id)

    def unpause(self):
        """Use self.PIPELINE_NAME as input to the unpause_pipeline function"""
        if self.PIPELINE_NAME:
            self.unpause_pipeline(self.PIPELINE_NAME)
        else:
            msg = "No default name specified for this pipeline"
            raise ValueError(msg)

    def trigger(self) -> int:
        """Use self.PIPELINE_NAME as input to the trigger_pipeline_build function"""
        if self.PIPELINE_NAME:
            return self.trigger_pipeline_build(self.PIPELINE_NAME)
        else:
            msg = "No default name specified for this pipeline"
            raise ValueError(msg)

    def upsert_config(self, config_str: str, pipeline_name: str):
        """Upsert the configuration for a pipeline"""
        config = json.dumps(yaml.load(config_str, Loader=yaml.SafeLoader))
        log.debug(config)
        # Try to get the pipeline_name of the pipeline if it already exists, because it will be  # noqa: E501
        # necessary to update an existing pipeline.
        url_path = self._make_pipeline_config_url(pipeline_name)
        try:
            _, headers = self.api.get_with_headers(url_path)
            version_headers = {
                "X-Concourse-Config-Version": headers["X-Concourse-Config-Version"]
            }
        except HTTPError:
            version_headers = None
        self.api.put_with_headers(url_path, data=config, headers=version_headers)

    def upsert_pipeline(self):
        """Placeholder for upsert_pipeline"""  # noqa: D401
        msg = "Choose a more specific pipeline class"
        raise NotImplementedError(msg)


class ThemeAssetsPipeline(GeneralPipeline, BaseThemeAssetsPipeline):
    """
    Concourse-CI pipeline for publishing theme assets
    """

    PIPELINE_NAME = BaseThemeAssetsPipeline.PIPELINE_NAME
    BRANCH = settings.GITHUB_WEBHOOK_BRANCH

    MANDATORY_SETTINGS = [
        *MANDATORY_CONCOURSE_SETTINGS,
        "AWS_ARTIFACTS_BUCKET_NAME",
        "AWS_PREVIEW_BUCKET_NAME",
        "AWS_PUBLISH_BUCKET_NAME",
        "GITHUB_WEBHOOK_BRANCH",
        "SEARCH_API_URL",
        "COURSE_SEARCH_API_URL",
        "CONTENT_FILE_SEARCH_API_URL",
    ]

    def __init__(
        self, themes_branch: Optional[str] = None, api: Optional[PipelineApi] = None
    ):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.BRANCH = themes_branch or get_theme_branch()
        self.set_instance_vars({"branch": self.BRANCH})

    def upsert_pipeline(self):
        """Upsert the theme assets pipeline"""
        template_vars = get_common_pipeline_vars()
        pipeline_definition = ThemeAssetsPipelineDefinition(
            artifacts_bucket=template_vars["artifacts_bucket_name"],
            preview_bucket=template_vars["preview_bucket_name"],
            publish_bucket=template_vars["publish_bucket_name"],
            test_bucket=template_vars["test_bucket_name"],
            ocw_hugo_themes_branch=self.BRANCH,
        )
        self.upsert_config(pipeline_definition.json(), self.PIPELINE_NAME)


class SitePipeline(BaseSitePipeline, GeneralPipeline):
    """
    Concourse-CI publishing pipeline, dependent on a Github backend, for individual sites
    """  # noqa: E501

    BRANCH = settings.GITHUB_WEBHOOK_BRANCH
    MANDATORY_SETTINGS = [
        *MANDATORY_CONCOURSE_SETTINGS,
        "AWS_ARTIFACTS_BUCKET_NAME",
        "AWS_PREVIEW_BUCKET_NAME",
        "AWS_PUBLISH_BUCKET_NAME",
        "AWS_OFFLINE_PREVIEW_BUCKET_NAME",
        "AWS_OFFLINE_PUBLISH_BUCKET_NAME",
        "AWS_STORAGE_BUCKET_NAME",
        "GIT_BRANCH_PREVIEW",
        "GIT_BRANCH_RELEASE",
        "GIT_DOMAIN",
        "GIT_ORGANIZATION",
        "GITHUB_WEBHOOK_BRANCH",
        "OCW_GTM_ACCOUNT_ID",
    ]

    def __init__(
        self,
        website: Website,
        hugo_args: Optional[str] = None,
        api: Optional[PipelineApi] = None,
    ):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.WEBSITE = website
        self.BRANCH = get_theme_branch()
        self.HUGO_ARGS = hugo_args
        self.set_instance_vars({"site": self.WEBSITE.name})

    def upsert_pipeline(
        self,
    ):  # pylint:disable=too-many-locals,too-many-statements
        """
        Create or update a concourse pipeline for the given Website
        """
        ocw_hugo_themes_branch = self.BRANCH
        ocw_hugo_projects_branch = (
            (settings.OCW_HUGO_PROJECTS_BRANCH or self.BRANCH)
            if is_dev()
            else self.BRANCH
        )

        starter = self.WEBSITE.starter
        if starter.source != STARTER_SOURCE_GITHUB:
            # This pipeline only handles sites with github-based starters
            return
        starter_path_url = urlparse(starter.path)
        if not starter_path_url.netloc:
            # Invalid github url, so skip
            return

        pipeline_vars = get_common_pipeline_vars()
        for branch_vars in [
            {
                "branch": settings.GIT_BRANCH_PREVIEW,
                "pipeline_name": VERSION_DRAFT,
            },
            {
                "branch": settings.GIT_BRANCH_RELEASE,
                "pipeline_name": VERSION_LIVE,
            },
        ]:
            pipeline_vars.update(branch_vars)
            branch = pipeline_vars["branch"]
            pipeline_name = pipeline_vars["pipeline_name"]
            storage_bucket = pipeline_vars["storage_bucket_name"]
            artifacts_bucket = pipeline_vars["artifacts_bucket_name"]
            if branch == settings.GIT_BRANCH_PREVIEW:
                web_bucket = pipeline_vars["preview_bucket_name"]
                offline_bucket = pipeline_vars["offline_preview_bucket_name"]
                static_api_base_url = pipeline_vars["static_api_base_url_draft"]
                resource_base_url = pipeline_vars["resource_base_url_draft"]
            elif branch == settings.GIT_BRANCH_RELEASE:
                web_bucket = pipeline_vars["publish_bucket_name"]
                offline_bucket = pipeline_vars["offline_publish_bucket_name"]
                static_api_base_url = pipeline_vars["static_api_base_url_live"]
                resource_base_url = pipeline_vars["resource_base_url_live"]
            pipeline_config = SitePipelineDefinitionConfig(
                site=self.WEBSITE,
                pipeline_name=pipeline_name,
                instance_vars=self.instance_vars,
                site_content_branch=branch,
                static_api_url=static_api_base_url,
                storage_bucket=storage_bucket,
                artifacts_bucket=artifacts_bucket,
                web_bucket=web_bucket,
                offline_bucket=offline_bucket,
                resource_base_url=resource_base_url,
                ocw_hugo_themes_branch=ocw_hugo_themes_branch,
                ocw_hugo_projects_branch=ocw_hugo_projects_branch,
                hugo_override_args=self.HUGO_ARGS,
            )
            self.upsert_config(
                SitePipelineDefinition(config=pipeline_config).json(), pipeline_name
            )


class MassBuildSitesPipeline(
    BaseMassBuildSitesPipeline, GeneralPipeline
):  # pylint: disable=too-many-instance-attributes
    """Specialized concourse pipeline for mass building multiple sites"""

    PIPELINE_NAME = BaseMassBuildSitesPipeline.PIPELINE_NAME

    def __init__(  # pylint: disable=too-many-arguments  # noqa: PLR0913
        self,
        version,
        api: Optional[PipelineApi] = None,
        prefix: Optional[str] = None,
        themes_branch: Optional[str] = None,
        projects_branch: Optional[str] = None,
        starter: Optional[str] = None,
        offline: Optional[bool] = None,
        hugo_args: Optional[str] = None,
    ):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = [
            *MANDATORY_CONCOURSE_SETTINGS,
            "AWS_ARTIFACTS_BUCKET_NAME",
            "AWS_PREVIEW_BUCKET_NAME",
            "AWS_PUBLISH_BUCKET_NAME",
            "AWS_OFFLINE_PREVIEW_BUCKET_NAME",
            "AWS_OFFLINE_PUBLISH_BUCKET_NAME",
            "AWS_STORAGE_BUCKET_NAME",
            "GIT_BRANCH_PREVIEW",
            "GIT_BRANCH_RELEASE",
            "GIT_DOMAIN",
            "GIT_ORGANIZATION",
            "GITHUB_WEBHOOK_BRANCH",
            "OCW_GTM_ACCOUNT_ID",
            "SEARCH_API_URL",
        ]
        super().__init__(api=api)
        self.pipeline_name = "mass_build_sites"
        self.VERSION = version
        self.PREFIX = prefix if prefix else ""
        self.THEMES_BRANCH = themes_branch if themes_branch else get_theme_branch()
        self.PROJECTS_BRANCH = (
            projects_branch if projects_branch else self.THEMES_BRANCH
        )
        self.STARTER = starter
        self.OFFLINE = offline
        self.HUGO_ARGS = hugo_args
        self.set_instance_vars(
            {
                "version": version,
                "themes_branch": self.THEMES_BRANCH,
                "projects_branch": self.PROJECTS_BRANCH,
                "prefix": self.PREFIX,
                "starter": self.STARTER,
                "offline": self.OFFLINE,
            }
        )

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """
        site_content_branch = get_site_content_branch(self.VERSION)
        pipeline_config = MassBuildSitesPipelineDefinitionConfig(
            version=self.VERSION,
            artifacts_bucket=settings.AWS_ARTIFACTS_BUCKET_NAME,
            site_content_branch=site_content_branch,
            ocw_hugo_themes_branch=self.THEMES_BRANCH,
            ocw_hugo_projects_branch=self.PROJECTS_BRANCH,
            offline=self.OFFLINE,
            prefix=self.PREFIX,
            instance_vars=self.instance_vars,
        )
        pipeline_definition = MassBuildSitesPipelineDefinition(config=pipeline_config)
        self.upsert_config(pipeline_definition.json(), self.PIPELINE_NAME)


class UnpublishedSiteRemovalPipeline(
    BaseUnpublishedSiteRemovalPipeline, GeneralPipeline
):
    """Specialized concourse pipeline for removing unpublished sites"""

    PIPELINE_NAME = BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME

    def __init__(self, api: Optional[PipelineApi] = None):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = [
            *MANDATORY_CONCOURSE_SETTINGS,
            "AWS_PUBLISH_BUCKET_NAME",
        ]
        super().__init__(api=api)
        self.pipeline_name = "remove_unpublished_sites"
        self.VERSION = VERSION_LIVE

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """

        self.upsert_config(
            UnpublishedSiteRemovalPipelineDefinition().json(), self.PIPELINE_NAME
        )


class TestPipeline(BaseTestPipeline, GeneralPipeline):
    """Concourse pipeline to run end to end tests from ocw-hugo-themes"""

    PIPELINE_NAME = BaseTestPipeline.PIPELINE_NAME

    def __init__(
        self,
        themes_branch: str,
        projects_branch: str,
        api: Optional[PipelineApi] = None,
    ):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = [
            *MANDATORY_CONCOURSE_SETTINGS,
            "AWS_TEST_BUCKET_NAME",
            "AWS_OFFLINE_TEST_BUCKET_NAME",
            "OCW_WWW_TEST_SLUG",
            "OCW_COURSE_TEST_SLUG",
            "STATIC_API_BASE_URL_TEST",
        ]
        super().__init__(api=api)
        self.VERSION = VERSION_LIVE
        self.THEMES_BRANCH = themes_branch or get_theme_branch()
        self.PROJECTS_BRANCH = projects_branch or get_projects_branch()

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """

        self.upsert_config(
            EndToEndTestPipelineDefinition(
                themes_branch=self.THEMES_BRANCH, projects_branch=self.PROJECTS_BRANCH
            ).json(),
            self.PIPELINE_NAME,
        )
