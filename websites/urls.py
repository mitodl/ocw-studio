""" websites URL Configuration
"""
from django.urls import include, re_path
from rest_framework_extensions.routers import ExtendedSimpleRouter as SimpleRouter

from websites import views


router = SimpleRouter()

website_route = router.register(
    r"websites", views.WebsiteViewSet, basename="websites_api"
)
mass_build_route = router.register(
    r"publish", views.WebsiteMassBuildViewSet, basename="mass_build_api"
)
unpublish_route = router.register(
    r"unpublish", views.WebsiteUnpublishViewSet, basename="unpublished_removal_api"
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
    re_path(r"^api/", include(router.urls)),
]
