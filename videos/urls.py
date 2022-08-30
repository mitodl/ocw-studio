""" Urls for video"""
from django.conf.urls import url

from videos.views import TranscodeJobView, TranscriptJobView, YoutubeTokensView


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
    url(r"api/youtube-tokens/", YoutubeTokensView.as_view(), name="yt_tokens"),
]
