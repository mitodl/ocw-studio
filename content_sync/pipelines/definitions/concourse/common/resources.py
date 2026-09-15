import os
from urllib.parse import urljoin, urlparse

from django.conf import settings
from ol_concourse.lib.models.pipeline import Identifier, Resource, ResourceType
from ol_concourse.lib.resource_types import (
    fastly_resource_type,
    slack_notification_resource,
)
from ol_concourse.lib.resources import fastly_service

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    FASTLY_RESOURCE_TYPE_IDENTIFIER,
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_OFFLINE_GATE_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    get_fastly_identifier,
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
        private_key: str | None = None,
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


class OcwStudioOfflineGateResource(Resource):
    """
    A Resource for making API calls to ocw-studio to check if a Website's
    offline version is downloadable.

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
            "api", "websites", site_name, "hide_download"
        )
        api_url = f"{urljoin(ocw_studio_url, api_path)}/"
        super().__init__(
            name=OCW_STUDIO_WEBHOOK_OFFLINE_GATE_IDENTIFIER,
            icon="language-python",
            type=HTTP_RESOURCE_TYPE_IDENTIFIER,
            check_every="never",
            source={
                "url": api_url,
                "method": "GET",
                "version": {"jq": ".version", "default": "none"},
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


# The MIT Learn distribution serves ocw-course-v3 content. Only live content reaches
# it, so it is purged alongside the live distribution and no other.
FASTLY_PURPOSE_LEARN = "learn"
# The distribution the e2e test pipeline publishes to. That pipeline runs under
# pipeline_name "live" but purges this distribution, which is why the MIT Learn purge
# is keyed off the Fastly purpose rather than the pipeline name.
FASTLY_PURPOSE_TEST = "test"


def get_fastly_domain(purpose: str) -> str | None:
    """
    Get the domain served by the Fastly distribution for a given purpose.

    The Fastly resource resolves the service ID from this domain at runtime, so no
    service IDs need to be stored in Concourse.

    Args:
        purpose(str): The distribution, e.g. "draft", "live", "test" or "learn"

    Returns:
        str | None: The domain, or None if none is configured for this environment
    """
    if purpose == FASTLY_PURPOSE_LEARN:
        return settings.COURSE_V3_CANONICAL_DOMAIN or None
    base_url = {
        VERSION_DRAFT: settings.OCW_STUDIO_DRAFT_URL,
        VERSION_LIVE: settings.OCW_STUDIO_LIVE_URL,
        FASTLY_PURPOSE_TEST: settings.STATIC_API_BASE_URL_TEST,
    }.get(purpose)
    if not base_url:
        return None
    return urlparse(base_url).netloc or None


def get_fastly_purge_purposes(purpose: str) -> list[str]:
    """
    Get every distribution that a build for a given purpose must purge.

    A distribution with no configured domain is omitted rather than raising, the same
    way is_dev() omits cache clearing entirely. CI, for example, has no OCW Fastly
    service at all.

    This is the single source of truth for both the purge steps and the Fastly
    resources a pipeline declares, so the two cannot drift apart.

    Args:
        purpose(str): The distribution being published to, e.g. "draft" or "live"

    Returns:
        list[str]: The distributions to purge, the given purpose first
    """
    purposes = [purpose]
    if purpose == VERSION_LIVE:
        purposes.append(FASTLY_PURPOSE_LEARN)
    return [item for item in purposes if get_fastly_domain(item)]


def fastly_resource_types(resources: list[Resource]) -> list[ResourceType]:
    """
    Get the ResourceType definitions required by any Fastly resources in a list.

    Derived from the resources themselves so a pipeline can never declare the
    resource type without the resources, or the resources without the type.

    Args:
        resources(list[Resource]): The resources a pipeline declares

    Returns:
        list[ResourceType]: The Fastly resource type, or empty if none is needed
    """
    if any(resource.type == FASTLY_RESOURCE_TYPE_IDENTIFIER for resource in resources):
        return [fastly_resource_type()]
    return []


def fastly_resources(purpose: str) -> list[Resource]:
    """
    Build the Fastly resources a pipeline publishing to a given purpose must declare.

    Args:
        purpose(str): The distribution being published to, e.g. "draft" or "live"

    Returns:
        list[Resource]: One Fastly resource per distribution that will be purged
    """
    return [
        fastly_service(
            name=get_fastly_identifier(item),
            api_token=settings.CONCOURSE_FASTLY_API_TOKEN_VAR,
            domain=get_fastly_domain(item),
            # Purge-only: never poll Fastly for VCL version changes. The library
            # default of "1h" would have every site pipeline instance polling.
            check_every="never",
        )
        for item in get_fastly_purge_purposes(purpose)
    ]
