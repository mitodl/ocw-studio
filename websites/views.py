""" Views for websites """
from django.contrib.auth.models import Group
from django.db.models import CharField, OuterRef, Q, Subquery, Value
from guardian.shortcuts import get_groups_with_perms, get_objects_for_user
from mitol.common.utils.datetime import now_in_utc
from rest_framework import mixins, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import LimitOffsetPagination
from rest_framework_extensions.mixins import NestedViewSetMixin

from main import features
from main.permissions import ReadonlyPermission
from users.models import User
from websites import constants
from websites.models import Website, WebsiteStarter
from websites.permissions import (
    HasWebsiteCollaborationPermission,
    HasWebsitePermission,
    is_global_admin,
)
from websites.serializers import (
    WebsiteCollaboratorSerializer,
    WebsiteDetailSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
)


class DefaultPagination(LimitOffsetPagination):
    """
    Pagination class for websites viewsets
    """

    default_limit = 10
    max_limit = 100


class WebsiteViewSet(
    NestedViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Viewset for Websites
    """

    serializer_class = WebsiteSerializer
    pagination_class = DefaultPagination
    permission_classes = (HasWebsitePermission,)
    lookup_field = "name"

    def get_queryset(self):
        """
        Generate a QuerySet for fetching websites.
        """
        ordering = self.request.query_params.get("sort", "-updated_on")
        website_type = self.request.query_params.get("type", None)

        user = self.request.user
        if self.request.user.is_anonymous:
            # Anonymous users should get a list of all published websites (used for ocw-www carousel)
            ordering = "-publish_date"
            queryset = Website.objects.filter(
                publish_date__lte=now_in_utc(),
            )
        elif is_global_admin(user):
            # Global admins should get a list of all websites, published or not.
            queryset = Website.objects.all()
        else:
            # Other authenticated users should get a list of websites they are editors/admins/owners for.
            queryset = get_objects_for_user(user, constants.PERMISSION_VIEW)
        if website_type is not None:
            queryset = queryset.filter(starter__slug=website_type)
        return queryset.select_related("starter").order_by(ordering)

    def get_serializer_class(self):
        if self.action == "list":
            return WebsiteSerializer
        else:
            return WebsiteDetailSerializer


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
            return WebsiteStarter.objects.filter(source=constants.STARTER_SOURCE_GITHUB)

    def get_serializer_class(self):
        if self.action == "list":
            return WebsiteStarterSerializer
        else:
            return WebsiteStarterDetailSerializer


class WebsiteCollaboratorViewSet(
    NestedViewSetMixin,
    viewsets.ModelViewSet,
):
    """ Viewset for Website collaborators along with their group/role """

    serializer_class = WebsiteCollaboratorSerializer
    permission_classes = (HasWebsiteCollaborationPermission,)
    pagination_class = DefaultPagination
    http_method_names = ["get", "post", "head", "patch", "delete"]  # No put
    lookup_field = "username"

    def get_queryset(self):
        """
        Get a list of all the users with permissions for this website, and annotate by group-name/role
        (owner, administrator, editor, or global administrator)
        """
        website = get_object_or_404(
            Website, name=self.kwargs.get("parent_lookup_website")
        )
        website_groups = list(
            get_groups_with_perms(website).values_list("name", flat=True)
        ) + [constants.GLOBAL_ADMIN]
        owner_username = website.owner.username if website.owner else None

        # Return the individual user and group if a primary key is provided
        if self.kwargs.get("username"):
            user_name = self.kwargs.get("username")
            if user_name == owner_username:
                return User.objects.filter(username=user_name).annotate(
                    group=Value(constants.ROLE_OWNER, CharField())
                )
            group_subquery = Group.objects.filter(
                Q(user__username=OuterRef("username")) & Q(name__in=website_groups)
            )
            return User.objects.filter(
                Q(username=user_name) & Q(groups__name__in=website_groups)
            ).annotate(group=Subquery(group_subquery.values("name")[:1]))

        # Otherwise get all the collaborators and annotate with the relevant group they are in
        query = User.objects.filter(username=owner_username).annotate(
            group=Value(constants.ROLE_OWNER, CharField())
        )
        for group_name in website_groups:
            query = query.union(
                Group.objects.get(name=group_name)
                .user_set.exclude(username=owner_username)
                .annotate(group=Value(group_name, CharField()))
            )
        return query.order_by("name")

    def perform_destroy(self, instance):
        """ Override this function, don't want to delete the user, just remove the user from groups"""
        website = Website.objects.get(name=self.kwargs.get("parent_lookup_website"))
        for group in get_groups_with_perms(website):
            instance.groups.remove(group)
