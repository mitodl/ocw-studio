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
from typing import Dict, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml
from concoursepy.api import Api as BaseConcourseApi
from django.conf import settings
from requests import HTTPError

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.decorators import retry_on_failure
from content_sync.pipelines.base import (
    BaseMassBuildSitesPipeline,
    BasePipeline,
    BaseSitePipeline,
    BaseThemeAssetsPipeline,
)
from content_sync.utils import check_mandatory_settings
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
from websites.models import Website
from websites.site_config_api import SiteConfig


log = logging.getLogger(__name__)

MANDATORY_CONCOURSE_SETTINGS = [
    "CONCOURSE_URL",
    "CONCOURSE_USERNAME",
    "CONCOURSE_PASSWORD",
]


class ConcourseApi(BaseConcourseApi):
    """
    Customized pipeline_name of concoursepy.api.Api that allows for getting/setting headers
    """

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


class ConcoursePipeline(BasePipeline):
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
        return ConcourseApi(
            settings.CONCOURSE_URL,
            settings.CONCOURSE_USERNAME,
            settings.CONCOURSE_PASSWORD,
            settings.CONCOURSE_TEAM,
        )

    def _make_builds_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching builds information"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}/builds{self.instance_vars}"

    def _make_pipeline_config_url(self, pipeline_name: str):
        """Make URL for fetching pipeline info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/config{self.instance_vars}"

    def _make_job_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching job info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}{self.instance_vars}"

    def _make_pipeline_unpause_url(self, pipeline_name: str):
        """Make URL for unpausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/unpause{self.instance_vars}"

    def trigger_pipeline_build(self, pipeline_name: str) -> int:
        """Trigger a pipeline build"""
        pipeline_info = self.api.get(self._make_pipeline_config_url(pipeline_name))
        job_name = pipeline_info["config"]["jobs"][0]["name"]
        return self.api.post(self._make_builds_url(pipeline_name, job_name))["id"]

    def unpause_pipeline(self, pipeline_name: str):
        """Unpause the pipeline"""
        self.api.put(self._make_pipeline_unpause_url(pipeline_name))

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


class SitePipeline(BaseSitePipeline, ConcoursePipeline):
    """
    Concourse-CI publishing pipeline, dependent on a Github backend, for individual sites
    """

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

    def __init__(self, website: Website, api: Optional[ConcourseApi] = None):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.website = website
        self.instance_vars = f'?vars={quote(json.dumps({"site": self.website.name}))}'

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update a concourse pipeline for the given Website
        """
        starter = self.website.starter
        if starter.source != STARTER_SOURCE_GITHUB:
            # This pipeline only handles sites with github-based starters
            return
        starter_path_url = urlparse(starter.path)
        if not starter_path_url.netloc:
            # Invalid github url, so skip
            return

        site_config = SiteConfig(self.website.starter.config)
        site_url = f"{site_config.root_url_path}/{self.website.name}".strip("/")
        if self.website.name == settings.ROOT_WEBSITE_NAME:
            base_url = ""
            theme_created_trigger = "true"
            theme_deployed_trigger = "false"
        else:
            base_url = site_url
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

        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            if branch == settings.GIT_BRANCH_PREVIEW:
                pipeline_name = VERSION_DRAFT
                destination_bucket = settings.AWS_PREVIEW_BUCKET_NAME
                static_api_url = settings.OCW_STUDIO_DRAFT_URL
            else:
                pipeline_name = VERSION_LIVE
                destination_bucket = settings.AWS_PUBLISH_BUCKET_NAME
                static_api_url = settings.OCW_STUDIO_LIVE_URL
            if settings.CONCOURSE_IS_PRIVATE_REPO:
                markdown_uri = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{self.website.short_id}.git"
                private_key_var = "\n      private_key: ((git-private-key))"
            else:
                markdown_uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{self.website.short_id}.git"
                private_key_var = ""
            build_drafts = "--buildDrafts" if pipeline_name == VERSION_DRAFT else ""

            with open(
                os.path.join(
                    os.path.dirname(__file__), "definitions/concourse/site-pipeline.yml"
                )
            ) as pipeline_config_file:
                config_str = (
                    pipeline_config_file.read()
                    .replace("((markdown-uri))", markdown_uri)
                    .replace("((git-private-key-var))", private_key_var)
                    .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
                    .replace("((ocw-bucket))", destination_bucket)
                    .replace(
                        "((ocw-hugo-themes-branch))", settings.GITHUB_WEBHOOK_BRANCH
                    )
                    .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
                    .replace(
                        "((ocw-hugo-projects-branch))", settings.GITHUB_WEBHOOK_BRANCH
                    )
                    .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
                    .replace("((ocw-studio-url))", settings.SITE_BASE_URL)
                    .replace("((static-api-base-url))", static_api_url)
                    .replace(
                        "((ocw-import-starter-slug))", settings.OCW_IMPORT_STARTER_SLUG
                    )
                    .replace("((ocw-studio-bucket))", settings.AWS_STORAGE_BUCKET_NAME)
                    .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
                    .replace(
                        "((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY
                    )
                    .replace("((ocw-site-repo))", self.website.short_id)
                    .replace("((ocw-site-repo-branch))", branch)
                    .replace("((config-slug))", self.website.starter.slug)
                    .replace("((base-url))", base_url)
                    .replace("((site-url))", site_url)
                    .replace("((site-name))", self.website.name)
                    .replace("((purge-url))", f"purge/{self.website.name}")
                    .replace("((purge_header))", purge_header)
                    .replace("((pipeline_name))", pipeline_name)
                    .replace("((api-token))", settings.API_BEARER_TOKEN or "")
                    .replace("((theme-deployed-trigger))", theme_deployed_trigger)
                    .replace("((theme-created-trigger))", theme_created_trigger)
                    .replace("((build-drafts))", build_drafts)
                )
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


class ThemeAssetsPipeline(ConcoursePipeline, BaseThemeAssetsPipeline):
    """
    Concourse-CI pipeline for publishing theme assets
    """

    PIPELINE_NAME = BaseThemeAssetsPipeline.PIPELINE_NAME

    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
        "GITHUB_WEBHOOK_BRANCH",
        "SEARCH_API_URL",
    ]

    def __init__(self, api: Optional[ConcourseApi] = None):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.instance_vars = (
            f'?vars={quote(json.dumps({"branch": settings.GITHUB_WEBHOOK_BRANCH}))}'
        )

    def upsert_pipeline(self):
        """Upsert the theme assets pipeline"""
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "definitions/concourse/theme-assets-pipeline.yml",
            )
        ) as pipeline_config_file:
            purge_header = (
                ""
                if settings.CONCOURSE_HARD_PURGE
                else "\n          - -H\n          - 'Fastly-Soft-Purge: 1'"
            )
            config_str = (
                pipeline_config_file.read()
                .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
                .replace("((ocw-hugo-themes-branch))", settings.GITHUB_WEBHOOK_BRANCH)
                .replace("((search-api-url))", settings.SEARCH_API_URL)
                .replace("((ocw-bucket-draft))", settings.AWS_PREVIEW_BUCKET_NAME)
                .replace("((ocw-bucket-live))", settings.AWS_PUBLISH_BUCKET_NAME)
                .replace("((purge_header))", purge_header)
            )
            config = json.dumps(yaml.load(config_str, Loader=yaml.SafeLoader))
            log.debug(config)
            # Try to get the pipeline_name of the pipeline if it already exists, because it will be
            # necessary to update an existing pipeline.
            url_path = self._make_pipeline_config_url(self.PIPELINE_NAME)
            try:
                _, headers = self.api.get_with_headers(url_path)
                version_headers = {
                    "X-Concourse-Config-Version": headers["X-Concourse-Config-Version"]
                }
            except HTTPError:
                version_headers = None
            self.api.put_with_headers(url_path, data=config, headers=version_headers)


class MassBuildSitesPipeline(BaseMassBuildSitesPipeline, ConcoursePipeline):
    """Specialized concourse pipeline for mass building multiple sites"""

    PIPELINE_NAME = BaseMassBuildSitesPipeline.PIPELINE_NAME

    def __init__(self, version, api: Optional[ConcourseApi] = None):
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
        ]
        super().__init__(api=api)
        self.pipeline_name = "mass_build_sites"
        self.version = version
        self.instance_vars = f'?vars={quote(json.dumps({"version": version}))}'

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """
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
            markdown_uri = f"git://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}"
            private_key_var = ""

        if self.version == VERSION_DRAFT:
            branch = settings.GIT_BRANCH_PREVIEW
            destination_bucket = settings.AWS_PREVIEW_BUCKET_NAME
            static_api_url = settings.OCW_STUDIO_DRAFT_URL
        else:
            branch = settings.GIT_BRANCH_RELEASE
            destination_bucket = settings.AWS_PUBLISH_BUCKET_NAME
            static_api_url = settings.OCW_STUDIO_LIVE_URL
        build_drafts = "--buildDrafts" if self.version == VERSION_DRAFT else ""

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "definitions/concourse/mass-build-sites.yml",
            )
        ) as pipeline_config_file:
            config_str = (
                pipeline_config_file.read()
                .replace("((markdown-uri))", markdown_uri)
                .replace("((git-private-key-var))", private_key_var)
                .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
                .replace("((ocw-bucket))", destination_bucket)
                .replace("((ocw-hugo-themes-branch))", settings.GITHUB_WEBHOOK_BRANCH)
                .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
                .replace("((ocw-hugo-projects-branch))", settings.GITHUB_WEBHOOK_BRANCH)
                .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
                .replace(
                    "((ocw-import-starter-slug))", settings.OCW_IMPORT_STARTER_SLUG
                )
                .replace("((ocw-studio-url))", settings.SITE_BASE_URL)
                .replace("((static-api-base-url))", static_api_url)
                .replace("((ocw-studio-bucket))", settings.AWS_STORAGE_BUCKET_NAME)
                .replace("((ocw-site-repo-branch))", branch)
                .replace("((version))", self.version)
                .replace("((api-token))", settings.API_BEARER_TOKEN or "")
                .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
                .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
                .replace("((build-drafts))", build_drafts)
            )
        log.debug(config_str)
        config = json.dumps(yaml.load(config_str, Loader=yaml.SafeLoader))
        # Try to get the version of the pipeline if it already exists, because it will be
        # necessary to update an existing pipeline.
        url_path = self._make_pipeline_config_url(self.PIPELINE_NAME)
        try:
            _, headers = self.api.get_with_headers(url_path)
            version_headers = {
                "X-Concourse-Config-Version": headers["X-Concourse-Config-Version"]
            }
        except HTTPError:
            version_headers = None
        self.api.put_with_headers(url_path, data=config, headers=version_headers)
