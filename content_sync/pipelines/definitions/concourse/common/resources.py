import os
from typing import Optional
from urllib.parse import urljoin

from django.conf import settings
from ol_concourse.lib.models.pipeline import Identifier, Resource
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.constants import DEV_ENDPOINT_URL
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    get_ocw_catalog_identifier,
)
from content_sync.utils import get_ocw_studio_api_url
from main.utils import is_dev
from websites.constants import OCW_HUGO_THEMES_GIT


class SlackAlertResource(Resource):
    """
    A Resource using the version of concourse-slack-notification specified by ol-concourse

    It sends messages to a Slack channel
    """  # noqa: E501

    def __init__(self, **kwargs):
        super().__init__(
            name=SLACK_ALERT_RESOURCE_IDENTIFIER,
            icon="slack",
            type=slack_notification_resource().name,
            check_every="never",
            source={"url": "((slack-url))", "disabled": "false"},
            **kwargs,
        )


class OpenCatalogResource(Resource):
    """
    A Resource that uses the http-resource ResourceType to trigger API calls to open catalog sites
    """  # noqa: E501

    def __init__(self, open_url, **kwargs):
        super().__init__(
            name=get_ocw_catalog_identifier(open_url),
            icon="cloud-search",
            type=HTTP_RESOURCE_TYPE_IDENTIFIER,
            check_every="never",
            source={
                "url": f"{open_url}",
                "method": "POST",
                "out_only": True,
                "headers": {
                    "Content-Type": "application/json",
                },
            },
            **kwargs,
        )


class GitResource(Resource):
    """
    A Resource for interacting with git repositories
    """

    def __init__(
        self,
        name: Identifier,
        uri: str,
        branch: str,
        private_key: Optional[str] = None,
        **kwagrs,
    ):
        super().__init__(
            name=name,
            icon="git",
            type="git",
            source={"uri": uri, "branch": branch},
            **kwagrs,
        )
        if private_key:
            self.source["private_key"] = private_key


class OcwStudioWebhookResource(Resource):
    """
    A Resource for making API calls ocw-studio to set a Website's status

    args:
        site_name(str): The name of the site the status is in reference to
        api_token(str): The ocw-studio API token
    """

    def __init__(
        self,
        site_name: str,
        api_token: str,
        **kwargs,
    ):
        ocw_studio_url = get_ocw_studio_api_url()
        api_path = os.path.join(  # noqa: PTH118
            "api", "websites", site_name, "pipeline_status"
        )
        api_url = f"{urljoin(ocw_studio_url, api_path)}/"
        super().__init__(
            name=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
            icon="language-python",
            type=HTTP_RESOURCE_TYPE_IDENTIFIER,
            check_every="never",
            source={
                "url": api_url,
                "method": "POST",
                "out_only": True,
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_token}",
                },
            },
            **kwargs,
        )


class WebpackManifestResource(Resource):
    """
    A Resource for fetching the ocw-hugo-themes webpack manifest from S3

    Args:
        bucket(str): The S3 bucket to fetch the file from
        branch(str): The branch of ocw-hugo-themes the webpack build was run on
    """

    def __init__(self, bucket: str, branch, **kwargs):
        super().__init__(
            type=S3_IAM_RESOURCE_TYPE_IDENTIFIER,
            icon="file-cloud",
            check_every="never",
            source={
                "bucket": bucket,
                "versioned_file": f"ocw-hugo-themes/{branch}/webpack.json",
            },
            **kwargs,
        )
        if is_dev():
            self.source.update(
                {
                    "endpoint": DEV_ENDPOINT_URL,
                    "access_key_id": (settings.AWS_ACCESS_KEY_ID or ""),
                    "secret_access_key": (settings.AWS_SECRET_ACCESS_KEY or ""),
                }
            )


class OcwHugoThemesGitResource(GitResource):
    """
    A GitResource for fetching the ocw-hugo-themes git repository

    Args:
        branch(str): The branch of ocw-hugo-themes to fetch
    """

    def __init__(self, branch: str, **kwargs):
        super().__init__(
            name=OCW_HUGO_THEMES_GIT_IDENTIFIER,
            uri=OCW_HUGO_THEMES_GIT,
            branch=branch,
            check_every="never",
            **kwargs,
        )


class OcwHugoProjectsGitResource(GitResource):
    """
    A GitResource for fetching the ocw-hugo-projcets git repository

    Args:
        branch(str): The branch of ocw-hugo-projects to fetch
    """

    def __init__(self, uri: str, branch: str, **kwargs):
        super().__init__(
            name=OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
            uri=uri,
            branch=branch,
            check_every="never",
            **kwargs,
        )


class SiteContentGitResource(GitResource):
    """
    A GitResource for fetching the site content git repository

    Args:
        branch(str): The branch of the site content repository to fetch
        short_id(str): The short_id property of the Website
    """

    def __init__(self, branch: str, short_id: str, **kwargs):
        if settings.CONCOURSE_IS_PRIVATE_REPO:
            uri = (
                f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{short_id}.git"
            )
            private_key = "((git-private-key))"
        else:
            uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{short_id}.git"
            private_key = None
        super().__init__(
            uri=uri,
            branch=branch,
            check_every="never",
            private_key=private_key,
            **kwargs,
        )
