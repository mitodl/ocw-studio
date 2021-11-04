""" Urls for video"""
from django.conf.urls import url

from videos.views import TranscodeJobView, TranscriptJobView


urlpatterns = [
    url(
        r"api/transcode-jobs/$",
        TranscodeJobView.as_view(),
        name="transcode_jobs",
    ),
    url(
        r"api/transcription-jobs/$",
        TranscriptJobView.as_view(),
        name="transcript_jobs",
    ),
]
