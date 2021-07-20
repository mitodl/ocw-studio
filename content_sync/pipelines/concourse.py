""" Concourse-CI preview/publish pipeline generator"""
import json
import logging
import os
from typing import Dict, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml
from concoursepy.api import Api as BaseConcourseApi
from django.conf import settings
from requests import HTTPError

from content_sync.apis.github import get_repo_name
from content_sync.decorators import retry_on_failure
from content_sync.pipelines.base import BaseSyncPipeline
from websites.constants import STARTER_SOURCE_GITHUB
from websites.models import Website
from websites.site_config_api import SiteConfig


log = logging.getLogger(__name__)


class ConcourseApi(BaseConcourseApi):
    """
    Customized version of concoursepy.api.Api that allows for getting/setting headers
    """

    def get_with_headers(
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
        super().post(path, data)

    @retry_on_failure
    def put(self, path, data=None):
        """Same as base put method but with a retry"""
        super().put(path, data)


class ConcourseGithubPipeline(BaseSyncPipeline):
    """
    Concourse-CI publishing pipeline, dependent on a Github backend
    """

    MANDATORY_SETTINGS = [
        "AWS_PREVIEW_BUCKET_NAME",
        "AWS_PUBLISH_BUCKET_NAME",
        "AWS_STORAGE_BUCKET_NAME",
        "CONCOURSE_URL",
        "CONCOURSE_USERNAME",
        "CONCOURSE_PASSWORD",
        "GIT_BRANCH_PREVIEW",
        "GIT_BRANCH_RELEASE",
        "GIT_DOMAIN",
        "GIT_ORGANIZATION",
        "GITHUB_WEBHOOK_BRANCH",
    ]

    def __init__(self, website: Website):
        """Initialize the pipeline API instance"""
        super().__init__(website)
        self.instance_vars = quote('{"site": "%s"}' % self.website.name)
        self.ci = ConcourseApi(
            settings.CONCOURSE_URL,
            settings.CONCOURSE_USERNAME,
            settings.CONCOURSE_PASSWORD,
            settings.CONCOURSE_TEAM,
        )

    def upsert_website_pipeline(self):  # pylint:disable=too-many-locals
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
        base_url = "" if self.website.name == settings.ROOT_WEBSITE_NAME else site_url
        purge_url = "purge_all" if not base_url else f"purge/{site_url}"
        hugo_projects_url = urljoin(
            f"{starter_path_url.scheme}://{starter_path_url.netloc}",
            f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git
        )

        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            if branch == settings.GIT_BRANCH_PREVIEW:
                version = "draft"
                destination_bucket = settings.AWS_PREVIEW_BUCKET_NAME
            else:
                version = "live"
                destination_bucket = settings.AWS_PUBLISH_BUCKET_NAME

            with open(
                os.path.join(
                    os.path.dirname(__file__), "definitions/concourse/site-pipeline.yml"
                )
            ) as pipeline_config_file:
                config_str = (
                    pipeline_config_file.read()
                    .replace("((git-domain))", settings.GIT_DOMAIN)
                    .replace("((github-org))", settings.GIT_ORGANIZATION)
                    .replace("((ocw-bucket))", destination_bucket)
                    .replace(
                        "((ocw-hugo-projects-branch))", settings.GITHUB_WEBHOOK_BRANCH
                    )
                    .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
                    .replace("((ocw-studio-url))", settings.SITE_BASE_URL)
                    .replace("((ocw-studio-bucket))", settings.AWS_STORAGE_BUCKET_NAME)
                    .replace("((ocw-site-repo))", get_repo_name(self.website))
                    .replace("((ocw-site-repo-branch))", branch)
                    .replace("((config-slug))", self.website.starter.slug)
                    .replace("((base-url))", base_url)
                    .replace("((site-url))", site_url)
                    .replace("((purge-url))", purge_url)
                )
            config = json.dumps(yaml.load(config_str, Loader=yaml.Loader))
            log.debug(config)
            # Try to get the version of the pipeline if it already exists, because it will be
            # necessary to update an existing pipeline.
            url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{version}/config?vars={self.instance_vars}"
            try:
                _, headers = self.ci.get_with_headers(url_path)
                version_headers = {
                    "X-Concourse-Config-Version": headers["X-Concourse-Config-Version"]
                }
            except HTTPError:
                version_headers = None
            self.ci.put_with_headers(url_path, data=config, headers=version_headers)
            self.ci.put(url_path.replace("/config", "/unpause"))
