"""
Script for getting access and refresh tokens for YouTube API OAuth credentials
"""

import os

from django.conf import settings
from django.core.management import BaseCommand
from google_auth_oauthlib.flow import InstalledAppFlow


script_path = os.path.dirname(os.path.realpath(__file__))


class Command(BaseCommand):
    """
    Interactive command to get YT_ACCESS_TOKEN, YT_REFRESH_TOKEN settings values required for YouTube uploads
    """

    def handle(self, *args, **options):
        """
        Run the command
        """
        oauth_config = {
            "installed": {
                "client_id": settings.YT_CLIENT_ID,
                "project_id": settings.YT_PROJECT_ID,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://accounts.google.com/o/oauth2/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": settings.YT_CLIENT_SECRET,
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(
            oauth_config,
            [
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/youtube.force-ssl",
                "https://www.googleapis.com/auth/youtube.upload",
            ],
        )
        credentials = flow.run_console()
        self.stdout.write(
            "YT_ACCESS_TOKEN={}\nYT_REFRESH_TOKEN={}\n".format(
                credentials.token, credentials.refresh_token
            )
        )
