"""Urls for video"""

from django.urls import path, re_path

from videos.views import TranscriptJobView, YoutubeTokensView

urlpatterns = [
    path(
        "api/transcription-jobs/",
        TranscriptJobView.as_view(),
        name="transcript_jobs",
    ),
    re_path(r"api/youtube-tokens/", YoutubeTokensView.as_view(), name="yt_tokens"),
]
