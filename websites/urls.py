""" websites URL Configuration
"""
from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from websites import views

router = SimpleRouter()

router.register(r"websites", views.WebsiteViewSet, basename="websites_api")

urlpatterns = [
    url(r"^api/", include(router.urls)),
]
