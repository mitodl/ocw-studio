""" websites URL Configuration
"""
from django.conf.urls import url
from django.urls import include
from rest_framework_extensions.routers import ExtendedSimpleRouter as SimpleRouter

from websites import views


router = SimpleRouter()

website_route = router.register(
    r"websites", views.WebsiteViewSet, basename="websites_api"
)
website_route.register(
    r"collaborators",
    views.WebsiteCollaboratorViewSet,
    basename="websites_collaborators_api",
    parents_query_lookups=["website"],
)
website_route.register(
    "content",
    views.WebsiteContentViewSet,
    basename="websites_content_api",
    parents_query_lookups=["website"],
)
router.register(
    r"starters", views.WebsiteStarterViewSet, basename="website_starters_api"
)

urlpatterns = [
    url(r"^api/", include(router.urls)),
]
