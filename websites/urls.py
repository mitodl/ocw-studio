""" websites URL Configuration
"""
from django.conf.urls import url
from django.urls import include
from rest_framework_extensions.routers import ExtendedSimpleRouter as SimpleRouter

from websites import views


router = SimpleRouter()

router.register(r"websites", views.WebsiteViewSet, basename="websites_api").register(
    r"collaborators",
    views.WebsiteCollaboratorViewSet,
    basename="websites_collaborators_api",
    parents_query_lookups=["website"],
)
router.register(
    r"starters", views.WebsiteStarterViewSet, basename="website_starters_api"
)

urlpatterns = [
    url(r"^api/", include(router.urls)),
]
