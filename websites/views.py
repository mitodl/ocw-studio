""" Views for websites """
from rest_framework import viewsets, mixins
from rest_framework.pagination import LimitOffsetPagination

from main import features
from main.permissions import ReadonlyPermission
from main.utils import now_in_utc
from websites.constants import STARTER_SOURCE_GITHUB
from websites.models import Website, WebsiteStarter
from websites.serializers import (
    WebsiteSerializer,
    WebsiteStarterSerializer,
    WebsiteStarterDetailSerializer,
)


class DefaultPagination(LimitOffsetPagination):
    """
    Pagination class for websites viewsets
    """

    default_limit = 10
    max_limit = 100


class WebsiteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Viewset for Websites
    """

    serializer_class = WebsiteSerializer
    pagination_class = DefaultPagination
    permission_classes = (ReadonlyPermission,)

    def get_queryset(self):
        """ Generate a QuerySet for fetching published websites """
        ordering = self.request.query_params.get("sort", "-publish_date")
        website_type = self.request.query_params.get("type", None)
        queryset = Website.objects.filter(
            publish_date__lte=now_in_utc(),
        ).order_by(ordering)
        if website_type is not None:
            queryset = queryset.filter(type=website_type)
        return queryset


class WebsiteStarterViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Viewset for WebsiteStarters
    """

    pagination_class = DefaultPagination
    permission_classes = (ReadonlyPermission,)

    def get_queryset(self):
        if features.is_enabled(features.USE_LOCAL_STARTERS):
            return WebsiteStarter.objects.all()
        else:
            return WebsiteStarter.objects.filter(source=STARTER_SOURCE_GITHUB)

    def get_serializer_class(self):
        if self.action == "list":
            return WebsiteStarterSerializer
        else:
            return WebsiteStarterDetailSerializer
