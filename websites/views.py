""" Views for websites """
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination

from main.permissions import ReadonlyPermission
from main.utils import now_in_utc
from websites.constants import WEBSITE_TYPE_COURSE
from websites.models import Website
from websites.serializers import WebsiteSerializer


class DefaultPagination(LimitOffsetPagination):
    """
    Pagination class for websites viewsets
    """

    default_limit = 10
    max_limit = 100


class WebsiteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,):
    """
    Viewset for Websites
    """

    serializer_class = WebsiteSerializer
    pagination_class = DefaultPagination
    permission_classes = (ReadonlyPermission,)

    def _get_base_queryset(self, *args, **kwargs):
        """Return the base queryset for all actions & exclude unpublished sites"""
        return Website.objects.filter(
            *args,
            **kwargs,
            publish_date__lte=now_in_utc(),
        )

    def get_queryset(self):
        """Generate a QuerySet for fetching valid courses"""
        return self._get_base_queryset()

    @action(methods=["GET"], detail=False, url_path=r"courses/new")
    def new_courses(self, request):
        """
        Get new courses
        """
        page = self.paginate_queryset(
            self._get_base_queryset(type=WEBSITE_TYPE_COURSE).order_by("-publish_date")
        )
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
