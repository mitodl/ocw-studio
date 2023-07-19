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
    def __init__(self, **kwargs):
        super().__init__(
            name=SLACK_ALERT_RESOURCE_IDENTIFIER,
            type=slack_notification_resource().name,
            check_every="never",
            source={"url": "((slack-url))", "disabled": "false"},
            **kwargs,
        )


class OpenDiscussionsResource(Resource):
    def __init__(self, **kwargs):
        super().__init__(
            name=OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
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
    def __init__(self, name: Identifier, uri: str, branch: str, **kwagrs):
        super().__init__(
            name=name, type="git", source={"uri": uri, "branch": branch}, **kwagrs
        )


class OcwStudioWebhookResource(Resource):
    def __init__(self, ocw_studio_url: str, site_name: str, api_token: str, **kwargs):
        super().__init__(
            name=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
            type=HTTP_RESOURCE_TYPE_IDENTIFIER,
            check_every="never",
            source={
                "url": f"{ocw_studio_url}/api/websites/{site_name}/pipeline_status/",
                "method": "POST",
                "out_only": True,
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_token}",
                },
            },
            **kwargs,
        )
