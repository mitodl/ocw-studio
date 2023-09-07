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
    DEV_ENDPOINT_URL,
    TARGET_OFFLINE,
    TARGET_ONLINE,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.decorators import retry_on_failure
from content_sync.pipelines.base import (
    BaseGeneralPipeline,
    BaseMassBuildSitesPipeline,
    BasePipelineApi,
    BaseSitePipeline,
    BaseThemeAssetsPipeline,
    BaseUnpublishedSiteRemovalPipeline,
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
    get_hugo_arg_string,
    get_theme_branch,
    strip_dev_lines,
    strip_non_dev_lines,
    strip_offline_lines,
    strip_online_lines,
)
from main.constants import PRODUCTION_NAMES
from main.utils import is_dev
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
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
        "GITHUB_WEBHOOK_BRANCH",
        "SEARCH_API_URL",
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

        for branch_vars in [
            {
                "branch": settings.GIT_BRANCH_PREVIEW,
                "pipeline_name": VERSION_DRAFT,
                "static_api_url": settings.STATIC_API_BASE_URL
                or settings.OCW_STUDIO_DRAFT_URL
                if is_dev()
                else settings.OCW_STUDIO_DRAFT_URL,
            },
            {
                "branch": settings.GIT_BRANCH_RELEASE,
                "pipeline_name": VERSION_LIVE,
                "static_api_url": settings.STATIC_API_BASE_URL
                or settings.OCW_STUDIO_LIVE_URL
                if is_dev()
                else settings.OCW_STUDIO_LIVE_URL,
            },
        ]:
            pipeline_vars = get_common_pipeline_vars()
            pipeline_vars.update(branch_vars)
            branch = pipeline_vars["branch"]
            pipeline_name = pipeline_vars["pipeline_name"]
            static_api_url = pipeline_vars["static_api_url"]
            storage_bucket = pipeline_vars["storage_bucket_name"]
            artifacts_bucket = pipeline_vars["artifacts_bucket_name"]
            if branch == settings.GIT_BRANCH_PREVIEW:
                web_bucket = pipeline_vars["preview_bucket_name"]
                offline_bucket = pipeline_vars["offline_preview_bucket_name"]
                resource_base_url = pipeline_vars["resource_base_url_draft"]
            elif branch == settings.GIT_BRANCH_RELEASE:
                web_bucket = pipeline_vars["publish_bucket_name"]
                offline_bucket = pipeline_vars["offline_publish_bucket_name"]
                resource_base_url = pipeline_vars["resource_base_url_live"]
            pipeline_config = SitePipelineDefinitionConfig(
                site=self.WEBSITE,
                pipeline_name=pipeline_name,
                instance_vars=self.instance_vars,
                site_content_branch=branch,
                static_api_url=static_api_url,
                storage_bucket=storage_bucket,
                artifacts_bucket=artifacts_bucket,
                web_bucket=web_bucket,
                offline_bucket=offline_bucket,
                resource_base_url=resource_base_url,
                ocw_studio_url=pipeline_vars["ocw_studio_url"],
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
        if prefix:
            self.PREFIX = prefix[1:] if prefix.startswith("/") else prefix
        else:
            self.PREFIX = ""
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
        template_vars = get_common_pipeline_vars()
        starter = Website.objects.get(name=settings.ROOT_WEBSITE_NAME).starter
        starter_path_url = urlparse(starter.path)
        hugo_projects_url = urljoin(
            f"{starter_path_url.scheme}://{starter_path_url.netloc}",
            f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git  # noqa: E501
        )
        if settings.CONCOURSE_IS_PRIVATE_REPO:
            markdown_uri = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}"
            private_key_var = "((git-private-key))"
        else:
            markdown_uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}"
            private_key_var = ""

        if self.VERSION == VERSION_DRAFT:
            template_vars.update(
                {
                    "branch": settings.GIT_BRANCH_PREVIEW,
                    "static_api_url": settings.STATIC_API_BASE_URL
                    or settings.OCW_STUDIO_DRAFT_URL
                    if is_dev()
                    else settings.OCW_STUDIO_DRAFT_URL,
                    "web_bucket": template_vars["preview_bucket_name"],
                    "offline_bucket": template_vars["offline_preview_bucket_name"],
                    "build_drafts": "--buildDrafts",
                    "resource_base_url": settings.RESOURCE_BASE_URL_DRAFT,
                    "noindex": "true",
                }
            )
        elif self.VERSION == VERSION_LIVE:
            template_vars.update(
                {
                    "branch": settings.GIT_BRANCH_RELEASE,
                    "static_api_url": settings.STATIC_API_BASE_URL
                    or settings.OCW_STUDIO_LIVE_URL
                    if is_dev()
                    else settings.OCW_STUDIO_LIVE_URL,
                    "web_bucket": template_vars["publish_bucket_name"],
                    "offline_bucket": template_vars["offline_publish_bucket_name"],
                    "build_drafts": "",
                    "resource_base_url": settings.RESOURCE_BASE_URL_LIVE,
                    "noindex": "true"
                    if settings.ENV_NAME not in PRODUCTION_NAMES
                    else "false",
                }
            )
        base_hugo_args = {
            "--themesDir": "../ocw-hugo-themes/",
            "--quiet": "",
        }
        base_online_args = base_hugo_args.copy()
        base_online_args.update(
            {
                "--baseURL": "$PREFIX/$BASE_URL",
                "--config": "../ocw-hugo-projects/$STARTER_SLUG/config.yaml",
            }
        )
        base_offline_args = base_hugo_args.copy()
        base_offline_args.update(
            {
                "--baseURL": "/",
                "--config": "../ocw-hugo-projects/$STARTER_SLUG/config-offline.yaml",
            }
        )
        hugo_args_online = get_hugo_arg_string(
            TARGET_ONLINE,
            self.VERSION,
            base_online_args,
            self.HUGO_ARGS,
        )
        hugo_args_offline = get_hugo_arg_string(
            TARGET_OFFLINE,
            self.VERSION,
            base_offline_args,
            self.HUGO_ARGS,
        )

        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/mass-build-sites.yml", offline=self.OFFLINE
            )
            .replace("((hugo-args-online))", hugo_args_online)
            .replace("((hugo-args-offline))", hugo_args_offline)
            .replace("((markdown-uri))", markdown_uri)
            .replace("((git-private-key-var))", private_key_var)
            .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
            .replace(
                "((artifacts-bucket))", template_vars["artifacts_bucket_name"] or ""
            )
            .replace("((web-bucket))", template_vars["web_bucket"] or "")
            .replace("((offline-bucket))", template_vars["offline_bucket"] or "")
            .replace("((ocw-hugo-themes-branch))", self.THEMES_BRANCH)
            .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
            .replace(
                "((ocw-hugo-projects-branch))",
                (settings.OCW_HUGO_PROJECTS_BRANCH or self.PROJECTS_BRANCH)
                if is_dev()
                else self.PROJECTS_BRANCH,
            )
            .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
            .replace("((ocw-import-starter-slug))", settings.OCW_COURSE_STARTER_SLUG)
            .replace("((ocw-course-starter-slug))", settings.OCW_COURSE_STARTER_SLUG)
            .replace("((ocw-studio-url))", template_vars["ocw_studio_url"] or "")
            .replace("((static-api-base-url))", template_vars["static_api_url"] or "")
            .replace("((ocw-studio-bucket))", settings.AWS_STORAGE_BUCKET_NAME or "")
            .replace("((ocw-site-repo-branch))", template_vars["branch"] or "")
            .replace("((version))", self.VERSION)
            .replace("((api-token))", settings.API_BEARER_TOKEN or "")
            .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
            .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
            .replace("((build-drafts))", template_vars["build_drafts"] or "")
            .replace("((sitemap-domain))", settings.SITEMAP_DOMAIN)
            .replace("((endpoint-url))", DEV_ENDPOINT_URL)
            .replace(
                "((cli-endpoint-url))",
                f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
            )
            .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
            .replace("((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or "")
            .replace("((resource-base-url))", template_vars["resource_base_url"])
            .replace("((prefix))", self.PREFIX)
            .replace("((search-api-url))", settings.SEARCH_API_URL)
            .replace("((starter))", f"&starter={self.STARTER}" if self.STARTER else "")
            .replace(
                "((trigger))",
                str(
                    self.THEMES_BRANCH == settings.GITHUB_WEBHOOK_BRANCH
                    and self.PROJECTS_BRANCH == settings.GITHUB_WEBHOOK_BRANCH
                ),
            )
            .replace(
                "((ocw-hugo-themes-sentry-dsn))",
                settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
            )
            .replace("((noindex))", template_vars["noindex"])
        )
        self.upsert_config(config_str, self.PIPELINE_NAME)


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
        template_vars = get_common_pipeline_vars()
        web_bucket = template_vars["publish_bucket_name"]
        offline_bucket = template_vars["offline_publish_bucket_name"]

        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/remove-unpublished-sites.yml"
            )
            .replace("((web-bucket))", web_bucket)
            .replace("((offline-bucket))", offline_bucket)
            .replace("((ocw-studio-url))", template_vars["ocw_studio_url"] or "")
            .replace("((version))", VERSION_LIVE)
            .replace("((api-token))", settings.API_BEARER_TOKEN or "")
            .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
            .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
            .replace(
                "((cli-endpoint-url))",
                f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
            )
            .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
            .replace("((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or "")
        )
        log.debug(config_str)
        self.upsert_config(config_str, self.PIPELINE_NAME)
