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
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml
from concoursepy.api import Api
from django.conf import settings
from requests import HTTPError

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_DRAFT, VERSION_LIVE
from content_sync.decorators import retry_on_failure
from content_sync.pipelines.base import (
    BaseGeneralPipeline,
    BaseMassBuildSitesPipeline,
    BasePipelineApi,
    BaseSitePipeline,
    BaseThemeAssetsPipeline,
    BaseUnpublishedSiteRemovalPipeline,
)
from content_sync.utils import (
    check_mandatory_settings,
    get_hugo_arg_string,
    get_template_vars,
    get_theme_branch,
    strip_dev_lines,
    strip_non_dev_lines,
    strip_offline_lines,
    strip_online_lines,
)
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
    """

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
        """ Same as the base class but with retries and support for concourse 7.7"""
        if self.has_username_and_passwd:
            self.ATC_AUTH = None
            session = self._set_new_session()
            # Get initial sky/login response
            r = session.get(urljoin(self.url, "/sky/login"))
            if r.status_code == 200:
                # Get second sky/login response based on the url found in the first response
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
                        raise ValueError("Invalid username and password")
                    if r.status_code == requests.codes.ok:
                        self.ATC_AUTH = self._get_skymarshal_auth()
                    else:
                        self._close_session()
        if self.ATC_AUTH:
            return True
        return False

    @retry_on_failure
    def get_with_headers(  # pylint:disable=too-many-branches
        self, path: str, stream: bool = False, iterator: bool = False
    ) -> Tuple[Dict, Dict]:
        """Customized base get method, returning response data and headers"""
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

    @retry_on_failure
    def put_with_headers(
        self, path: str, data: Dict = None, headers: Dict = None
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
        """Same as base post method but with a retry"""
        return super().post(path, data)

    @retry_on_failure
    def put(self, path, data=None):
        """Same as base put method but with a retry"""
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

    def get_pipelines(self, names: List[str] = None):
        """Retrieve a list of concourse pipelines, filtered by team and optionally name"""
        pipelines = super().list_pipelines(settings.CONCOURSE_TEAM)
        if names:
            pipelines = [
                pipeline for pipeline in pipelines if pipeline["name"] in names
            ]
        return pipelines

    def delete_pipelines(self, names: List[str] = None):
        """Delete all pipelines matching filters"""
        pipeline_list = self.get_pipelines(names)
        for item in pipeline_list:
            pipeline = GeneralPipeline(api=self)
            instance_vars = item.get("instance_vars")
            if instance_vars:
                pipeline.set_instance_vars(instance_vars)
            pipeline.delete_pipeline(item["name"])


class GeneralPipeline(BaseGeneralPipeline):
    """ Base class for a Concourse pipeline """

    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS
    PIPELINE_NAME = None

    def __init__(
        self, *args, api: Optional[object] = None, **kwargs
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
        with open(
            os.path.join(os.path.dirname(__file__), pipeline_file)
        ) as pipeline_config_file:
            pipeline_config = pipeline_config_file.read()
            pipeline_config = (
                strip_non_dev_lines(pipeline_config)
                if is_dev()
                else strip_dev_lines(pipeline_config)
            )
            pipeline_config = (
                strip_online_lines(pipeline_config)
                if offline
                else strip_offline_lines(pipeline_config)
            )
            return pipeline_config

    def set_instance_vars(self, instance_vars: Dict):
        """Set the instance vars for the pipeline"""
        self.instance_vars = f"?vars={quote(json.dumps(instance_vars))}"

    def _make_pipeline_url(self, pipeline_name: str):
        """Make URL for getting/destroying a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}{self.instance_vars}"

    def _make_builds_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching builds information"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}/builds{self.instance_vars}"

    def _make_pipeline_config_url(self, pipeline_name: str):
        """Make URL for fetching pipeline info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/config{self.instance_vars}"

    def _make_job_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching job info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}{self.instance_vars}"

    def _make_pipeline_pause_url(self, pipeline_name: str):
        """Make URL for pausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/pause{self.instance_vars}"

    def _make_pipeline_unpause_url(self, pipeline_name: str):
        """Make URL for unpausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/unpause{self.instance_vars}"

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
        """ Use self.PIPELINE_NAME as input to the unpause_pipeline function"""
        if self.PIPELINE_NAME:
            self.unpause_pipeline(self.PIPELINE_NAME)
        else:
            raise ValueError("No default name specified for this pipeline")

    def trigger(self) -> int:
        """ Use self.PIPELINE_NAME as input to the trigger_pipeline_build function"""
        if self.PIPELINE_NAME:
            return self.trigger_pipeline_build(self.PIPELINE_NAME)
        else:
            raise ValueError("No default name specified for this pipeline")

    def upsert_config(self, config_str: str, pipeline_name: str):
        """Upsert the configuration for a pipeline"""
        config = json.dumps(yaml.load(config_str, Loader=yaml.SafeLoader))
        log.debug(config)
        # Try to get the pipeline_name of the pipeline if it already exists, because it will be
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
        """Placeholder for upsert_pipeline"""
        raise NotImplementedError("Choose a more specific pipeline class")


class SitePipeline(BaseSitePipeline, GeneralPipeline):
    """
    Concourse-CI publishing pipeline, dependent on a Github backend, for individual sites
    """

    BRANCH = settings.GITHUB_WEBHOOK_BRANCH
    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
        "AWS_PREVIEW_BUCKET_NAME",
        "AWS_PUBLISH_BUCKET_NAME",
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
        hugo_args: Optional[str],
        api: Optional[PipelineApi] = None,
    ):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.WEBSITE = website
        self.BRANCH = get_theme_branch()
        self.HUGO_ARGS = hugo_args
        self.set_instance_vars({"site": self.WEBSITE.name})

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
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

        if self.WEBSITE.name == settings.ROOT_WEBSITE_NAME:
            base_url = ""
            theme_created_trigger = "true"
            theme_deployed_trigger = "false"
        else:
            base_url = self.WEBSITE.get_url_path()
            theme_created_trigger = "false"
            theme_deployed_trigger = "true"
        hugo_projects_url = urljoin(
            f"{starter_path_url.scheme}://{starter_path_url.netloc}",
            f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git
        )
        purge_header = (
            ""
            if settings.CONCOURSE_HARD_PURGE
            else "\n              - -H\n              - 'Fastly-Soft-Purge: 1'"
        )
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
            branch_vars.update(get_template_vars())
            branch = branch_vars["branch"]
            pipeline_name = branch_vars["pipeline_name"]
            static_api_url = branch_vars["static_api_url"]
            storage_bucket_name = branch_vars["storage_bucket_name"]
            artifacts_bucket = branch_vars["artifacts_bucket_name"]
            if branch == settings.GIT_BRANCH_PREVIEW:
                destination_bucket = branch_vars["preview_bucket_name"]
                resource_base_url = branch_vars["resource_base_url_draft"]
            elif branch == settings.GIT_BRANCH_RELEASE:
                destination_bucket = branch_vars["publish_bucket_name"]
                resource_base_url = branch_vars["resource_base_url_live"]

            if settings.CONCOURSE_IS_PRIVATE_REPO:
                markdown_uri = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{self.WEBSITE.short_id}.git"
                private_key_var = "\n      private_key: ((git-private-key))"
            else:
                markdown_uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{self.WEBSITE.short_id}.git"
                private_key_var = ""
            hugo_arg_string = get_hugo_arg_string(
                base_url, self.WEBSITE.starter.slug, pipeline_name, self.HUGO_ARGS
            )
            config_str = (
                self.get_pipeline_definition("definitions/concourse/site-pipeline.yml")
                .replace("((hugo-args))", hugo_arg_string)
                .replace("((markdown-uri))", markdown_uri)
                .replace("((git-private-key-var))", private_key_var)
                .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
                .replace("((artifacts-bucket))", artifacts_bucket or "")
                .replace("((ocw-bucket))", destination_bucket or "")
                .replace("((ocw-hugo-themes-branch))", ocw_hugo_themes_branch)
                .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
                .replace("((ocw-hugo-projects-branch))", ocw_hugo_projects_branch)
                .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
                .replace("((ocw-studio-url))", branch_vars["ocw_studio_url"] or "")
                .replace("((static-api-base-url))", static_api_url)
                .replace(
                    "((ocw-import-starter-slug))", settings.OCW_COURSE_STARTER_SLUG
                )
                .replace(
                    "((ocw-course-starter-slug))", settings.OCW_COURSE_STARTER_SLUG
                )
                .replace("((ocw-studio-bucket))", storage_bucket_name or "")
                .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
                .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
                .replace("((short-id))", self.WEBSITE.short_id)
                .replace("((ocw-site-repo-branch))", branch)
                .replace("((config-slug))", self.WEBSITE.starter.slug)
                .replace("((s3-path))", self.WEBSITE.s3_path)
                .replace("((base-url))", base_url)
                .replace("((site-url))", self.WEBSITE.get_url_path())
                .replace("((site-name))", self.WEBSITE.name)
                .replace("((purge-url))", f"purge/{self.WEBSITE.name}")
                .replace("((purge_header))", purge_header)
                .replace("((pipeline_name))", pipeline_name)
                .replace("((api-token))", settings.API_BEARER_TOKEN or "")
                .replace("((theme-deployed-trigger))", theme_deployed_trigger)
                .replace("((theme-created-trigger))", theme_created_trigger)
                .replace("((build-drafts))", build_drafts)
                .replace("((sitemap-domain))", settings.SITEMAP_DOMAIN)
                .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
                .replace(
                    "((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or ""
                )
                .replace("((endpoint-url))", DEV_ENDPOINT_URL)
                .replace(
                    "((cli-endpoint-url))",
                    f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
                )
                .replace("((resource-base-url))", resource_base_url or "")
                .replace(
                    "((ocw-hugo-themes-sentry-dsn))",
                    settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
                )
                .replace(
                    "((delete))",
                    ""
                    if self.WEBSITE.name == settings.ROOT_WEBSITE_NAME
                    else " --delete",
                )
            )
            self.upsert_config(config_str, pipeline_name)


class ThemeAssetsPipeline(GeneralPipeline, BaseThemeAssetsPipeline):
    """
    Concourse-CI pipeline for publishing theme assets
    """

    PIPELINE_NAME = BaseThemeAssetsPipeline.PIPELINE_NAME
    BRANCH = settings.GITHUB_WEBHOOK_BRANCH

    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
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
        template_vars = get_template_vars()
        purge_header = (
            ""
            if settings.CONCOURSE_HARD_PURGE
            else "\n          - -H\n          - 'Fastly-Soft-Purge: 1'"
        )
        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/theme-assets-pipeline.yml"
            )
            .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
            .replace("((ocw-hugo-themes-branch))", self.BRANCH)
            .replace("((search-api-url))", settings.SEARCH_API_URL)
            .replace("((ocw-bucket-draft))", template_vars["preview_bucket_name"] or "")
            .replace("((ocw-bucket-live))", template_vars["publish_bucket_name"] or "")
            .replace(
                "((artifacts-bucket))", template_vars["artifacts_bucket_name"] or ""
            )
            .replace("((purge_header))", purge_header)
            .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
            .replace("((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or "")
            .replace(
                "((cli-endpoint-url))",
                f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
            )
            .replace(
                "((ocw-hugo-themes-sentry-dsn))",
                settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
            )
            .replace("((atc-search-params))", self.instance_vars)
        )
        self.upsert_config(config_str, self.PIPELINE_NAME)


class MassBuildSitesPipeline(
    BaseMassBuildSitesPipeline, GeneralPipeline
):  # pylint: disable=too-many-instance-attributes
    """Specialized concourse pipeline for mass building multiple sites"""

    PIPELINE_NAME = BaseMassBuildSitesPipeline.PIPELINE_NAME

    def __init__(  # pylint: disable=too-many-arguments
        self,
        version,
        api: Optional[PipelineApi] = None,
        prefix: Optional[str] = None,
        themes_branch: Optional[str] = None,
        projects_branch: Optional[str] = None,
        starter: Optional[str] = None,
        offline: Optional[bool] = None,
    ):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
            "AWS_PREVIEW_BUCKET_NAME",
            "AWS_PUBLISH_BUCKET_NAME",
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
        template_vars = get_template_vars()
        starter = Website.objects.get(name=settings.ROOT_WEBSITE_NAME).starter
        starter_path_url = urlparse(starter.path)
        hugo_projects_url = urljoin(
            f"{starter_path_url.scheme}://{starter_path_url.netloc}",
            f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git
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
                    "destination_bucket": template_vars["preview_bucket_name"],
                    "build_drafts": "--buildDrafts",
                    "resource_base_url": settings.RESOURCE_BASE_URL_DRAFT,
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
                    "destination_bucket": template_vars["publish_bucket_name"],
                    "build_drafts": "",
                    "resource_base_url": settings.RESOURCE_BASE_URL_LIVE,
                }
            )

        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/mass-build-sites.yml", offline=self.OFFLINE
            )
            .replace("((markdown-uri))", markdown_uri)
            .replace("((git-private-key-var))", private_key_var)
            .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
            .replace(
                "((artifacts-bucket))", template_vars["artifacts_bucket_name"] or ""
            )
            .replace("((ocw-bucket))", template_vars["destination_bucket"] or "")
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
        )
        self.upsert_config(config_str, self.PIPELINE_NAME)


class UnpublishedSiteRemovalPipeline(
    BaseUnpublishedSiteRemovalPipeline, GeneralPipeline
):
    """Specialized concourse pipeline for removing unpublished sites"""

    PIPELINE_NAME = BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME

    def __init__(self, api: Optional[PipelineApi] = None):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
            "AWS_PUBLISH_BUCKET_NAME"
        ]
        super().__init__(api=api)
        self.pipeline_name = "remove_unpublished_sites"
        self.VERSION = VERSION_LIVE

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """
        template_vars = get_template_vars()
        destination_bucket = template_vars["publish_bucket_name"]

        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/remove-unpublished-sites.yml"
            )
            .replace("((ocw-bucket))", destination_bucket)
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
