"""URLs for OCW News"""
from django.urls import path

from news.views import news


urlpatterns = [
    path("api/news/", news, name="ocw-news"),
]
