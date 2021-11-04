"""Video sync views"""
import json
import logging

import requests
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from videos.api import update_video_job
from videos.constants import VideoStatus
from videos.models import Video, VideoJob
from videos.tasks import update_transcripts_for_video


log = logging.getLogger()


class TranscodeJobView(GenericAPIView):
    """ Webhook endpoint for MediaConvert transcode job notifications from Cloudwatch"""

    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """ Update Video and VideoFile objects based on request body """
        message = json.loads(request.body)
        if message.get("SubscribeURL"):
            # Confirm the subscription
            if settings.AWS_ACCOUNT_ID not in message.get("TopicArn", ""):
                raise PermissionDenied
            requests.get(message.get("SubscribeURL"))
        else:
            if settings.AWS_ACCOUNT_ID != message.get("account", ""):
                raise PermissionDenied
            detail = message.get("detail", {})
            video_job = VideoJob.objects.get(job_id=detail.get("jobId"))
            update_video_job(video_job, detail)
        return Response(status=200, data={})


class TranscriptJobView(GenericAPIView):
    """ Webhook endpoint for transcript completion notifications from 3play"""

    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """ Update transcripts """
        video_id = request.query_params.get("video_id")
        api_key = request.query_params.get("callback_key")

        if video_id and api_key and (api_key == settings.THREEPLAY_CALLBACK_KEY):
            video = Video.objects.filter(pk=video_id).last()
            if video and video.status == VideoStatus.SUBMITTED_FOR_TRANSCRIPTION:
                update_transcripts_for_video.delay(video.id)

        return Response(status=200, data={})
