import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from main import settings

client = WebClient(token=settings.SLACK_NOTIFICATION_BOT)
log = logging.getLogger()


def post_message(channel: str, body: str):
    try:
        client.chat_postMessage(
            channel=channel if channel.startswith("#") else f"#{channel}", text=body
        )

    except SlackApiError as error:
        log.exception(error.response["error"])
