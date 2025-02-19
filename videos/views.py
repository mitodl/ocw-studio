"""Video sync views"""

import logging
from urllib.parse import urljoin

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from google_auth_oauthlib.flow import InstalledAppFlow
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from videos.constants import VideoStatus
from videos.models import Video
from videos.tasks import update_transcripts_for_video

log = logging.getLogger()


class TranscriptJobView(GenericAPIView):
    """Webhook endpoint for transcript completion notifications from 3play"""

    permission_classes = (AllowAny,)

    def post(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):  # pylint: disable=unused-argument
        """Update transcripts"""
        video_id = request.query_params.get("video_id")
        api_key = request.query_params.get("callback_key")

        if video_id and api_key and (api_key == settings.THREEPLAY_CALLBACK_KEY):
            video = Video.objects.filter(pk=video_id).last()
            if video and video.status == VideoStatus.SUBMITTED_FOR_TRANSCRIPTION:
                update_transcripts_for_video.delay(video.id)

        return Response(status=200, data={})


class YoutubeTokensView(GenericAPIView):
    """Admin-only endpoint for generating new Youtube OAuth tokens"""

    permission_classes = (IsAdminUser,)

    def get(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):  # pylint: disable=unused-argument
        """Return Youtube credential info"""
        token_url = urljoin(settings.SITE_BASE_URL, reverse("yt_tokens"))
        oauth_config = {
            "installed": {
                "client_id": settings.YT_CLIENT_ID,
                "client_secret": settings.YT_CLIENT_SECRET,
                "project_id": settings.YT_PROJECT_ID,
                "redirect_uris": [token_url],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://accounts.google.com/o/oauth2/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
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

        if not request.query_params.get("code"):
            authorization_url, _ = flow.authorization_url(
                access_type="offline", prompt="consent", include_granted_scopes="true"
            )
            return redirect(f"{authorization_url}&redirect_uri={token_url}")
        else:
            flow.redirect_uri = token_url
            flow.fetch_token(authorization_response=request.build_absolute_uri())
            credentials = flow.credentials
            output = {
                "YT_ACCESS_TOKEN": credentials.token,
                "YT_REFRESH_TOKEN": credentials.refresh_token,
            }
            return Response(output)
