""" Concourse-CI preview/publish pipeline generator"""
import json
import logging
import os
from typing import Dict, Tuple
from urllib.parse import quote

import requests
import yaml
from concoursepy.api import Api as BaseConcourseApi
from django.conf import settings
from requests import HTTPError

from content_sync.apis.github import get_repo_name
from content_sync.pipelines.base import BaseSyncPipeline
from websites.site_config_api import SiteConfig


log = logging.getLogger(__name__)


class ConcourseApi(BaseConcourseApi):
    """
    Customized version of concoursepy.api.Api
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

    def upsert_website_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update a concourse pipeline for the given Website
        """
        site_config = SiteConfig(self.website.starter.config)
        site_url = f"{site_config.root_url_path}/{self.website.name}".strip("/")
        base_url = "" if self.website.name == settings.ROOT_WEBSITE_NAME else site_url
        purge_url = "purge_all" if not base_url else f"purge/{site_url}"

        ci = ConcourseApi(
            settings.CONCOURSE_URL,
            settings.CONCOURSE_USERNAME,
            settings.CONCOURSE_PASSWORD,
            settings.CONCOURSE_TEAM,
        )
        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            if branch == settings.GIT_BRANCH_PREVIEW:
                version = "draft"
                destination_bucket = settings.AWS_PREVIEW_BUCKET_NAME
            else:
                version = "live"
                destination_bucket = settings.AWS_PUBLISH_BUCKET_NAME
            instance_vars = "{" + quote(f'"site": "{self.website.name}"') + "}"

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
            url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{version}/config?vars={instance_vars}"
            try:
                _, headers = ci.get_with_headers(url_path)
                version_headers = {
                    "X-Concourse-Config-Version": headers["X-Concourse-Config-Version"]
                }
            except HTTPError:
                version_headers = None
            success = False
            attempts = 0
            # Usually takes 2 tries because the first fails with a 401 :(
            while attempts < 2 and not success:
                try:
                    ci.put_with_headers(url_path, data=config, headers=version_headers)
                    success = True
                except:  # pylint:disable=bare-except
                    attempts += 1
            ci.put(url_path.replace("/config", "/unpause"))
