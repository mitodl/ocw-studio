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
from videos.models import VideoJob


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
