""" websites URL Configuration
"""
from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter

from websites import views

router = DefaultRouter()

router.register(r"websites", views.WebsiteViewSet, basename="websites")

urlpatterns = [
    url(r"^api/", include(router.urls)),
]
