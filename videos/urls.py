""" Urls for video"""
from django.conf.urls import url

from videos.views import TranscodeJobView


urlpatterns = [
    url(
        r"api/transcode-jobs/$",
        TranscodeJobView.as_view(),
        name="transcode_jobs",
    )
]
