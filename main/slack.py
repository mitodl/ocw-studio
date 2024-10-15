import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from main import settings

client = WebClient(token=settings.SLACK_NOTIFICATION_BOT_TOKEN)
log = logging.getLogger()


def post_message(channel_id: str, body: str):
    """Post message to provided channel ID."""

    try:
        client.chat_postMessage(channel=channel_id, text=body)

    except SlackApiError as error:
        log.exception(error.response["error"])
