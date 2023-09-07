"""Urls for video"""
from django.urls import re_path

from videos.views import TranscodeJobView, TranscriptJobView, YoutubeTokensView

urlpatterns = [
    re_path(
        r"api/transcode-jobs/$",
        TranscodeJobView.as_view(),
        name="transcode_jobs",
    ),
    re_path(
        r"api/transcription-jobs/$",
        TranscriptJobView.as_view(),
        name="transcript_jobs",
    ),
    re_path(r"api/youtube-tokens/", YoutubeTokensView.as_view(), name="yt_tokens"),
]
