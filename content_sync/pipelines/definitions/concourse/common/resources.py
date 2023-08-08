import os
from urllib.parse import urljoin

from django.conf import settings
from ol_concourse.lib.models.pipeline import Identifier, Resource
from ol_concourse.lib.resource_types import slack_notification_resource

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
)


class SlackAlertResource(Resource):
    """
    A Resource using the version of concourse-slack-notification specified by ol-concourse

    It sends messages to a Slack channel
    """

    def __init__(self, **kwargs):
        super().__init__(
            name=SLACK_ALERT_RESOURCE_IDENTIFIER,
            icon="slack",
            type=slack_notification_resource().name,
            check_every="never",
            source={"url": "((slack-url))", "disabled": "false"},
            **kwargs,
        )


class OpenDiscussionsResource(Resource):
    """
    A Resource that uses the http-resource ResourceType to trigger API calls to open-discussions
    """

    def __init__(self, **kwargs):
        super().__init__(
            name=OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
            icon="cloud-search",
            type=HTTP_RESOURCE_TYPE_IDENTIFIER,
            check_every="never",
            source={
                "url": f"{settings.OPEN_DISCUSSIONS_URL}/api/v0/ocw_next_webhook/",
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

    def __init__(self, name: Identifier, uri: str, branch: str, **kwagrs):
        super().__init__(
            name=name,
            icon="git",
            type="git",
            source={"uri": uri, "branch": branch},
            **kwagrs,
        )


class OcwStudioWebhookResource(Resource):
    """
    A Resource for making API calls ocw-studio to set a Website's status

    args:
        ocw_studio_url(str): The URL to the instance of ocw-studio to POST to
        site_name(str): The name of the site the status is in reference to
        api_token(str): The ocw-studio API token
    """

    def __init__(self, ocw_studio_url: str, site_name: str, api_token: str, **kwargs):
        api_path = os.path.join("api", "websites", site_name, "pipeline_status")
        api_url = f"{urljoin(ocw_studio_url, api_path)}/"
        super().__init__(
            name=Identifier(
                f"{OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER}-{site_name}"
            ),
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
