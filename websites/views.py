""" Views for websites """
from django.contrib.auth.models import Group
from django.db.models import Case, CharField, OuterRef, Q, Value, When
from django.utils.functional import cached_property
from django.utils.text import slugify
from guardian.shortcuts import get_groups_with_perms, get_objects_for_user
from mitol.common.utils.datetime import now_in_utc
from rest_framework import mixins, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from main import features
from main.permissions import ReadonlyPermission
from main.views import DefaultPagination
from users.models import User
from websites import constants
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.permissions import (
    HasWebsiteCollaborationPermission,
    HasWebsiteContentPermission,
    HasWebsitePermission,
    is_global_admin,
)
from websites.serializers import (
    WebsiteCollaboratorSerializer,
    WebsiteContentCreateSerializer,
    WebsiteContentDetailSerializer,
    WebsiteContentSerializer,
    WebsiteDetailSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
    WebsiteWriteSerializer,
)
from websites.site_config_api import find_config_item, is_page_content
from websites.utils import permissions_group_name_for_role


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
        elif self.action == "create":
            return WebsiteWriteSerializer
        else:
            return WebsiteDetailSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs["context"] = self.get_serializer_context()

        # If a new website is being created, and the request includes a title but not a name, auto-generate the
        # name by slugify-ing the title before passing the data off to the serializer.
        if (
            self.request.method == "POST"
            and "name" not in self.request.data
            and self.request.data.get("title")
        ):
            request_data = self.request.data.copy()
            request_data["name"] = slugify(request_data["title"])
            kwargs["data"] = request_data

        return serializer_class(*args, **kwargs)


class WebsiteStarterViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Viewset for WebsiteStarters
    """

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
    lookup_url_kwarg = "user_id"

    @cached_property
    def website(self):
        """Fetches the Website for this request"""
        return get_object_or_404(Website, name=self.kwargs.get("parent_lookup_website"))

    def get_queryset(self):
        """
        Builds a queryset of relevant users with permissions for this website, and annotates them by group name/role
        (owner, administrator, editor, or global administrator)
        """
        website = self.website
        website_group_names = list(
            get_groups_with_perms(website).values_list("name", flat=True)
        ) + [constants.GLOBAL_ADMIN]
        owner_user_id = website.owner.id if website.owner else None

        return (
            User.objects.filter(
                Q(id=owner_user_id) | Q(groups__name__in=website_group_names)
            )
            .annotate(
                role=Case(
                    When(id=owner_user_id, then=Value(constants.ROLE_OWNER)),
                    default=Group.objects.filter(
                        user__id=OuterRef("id"), name__in=website_group_names
                    )
                    .annotate(
                        role_name=Case(
                            *(
                                [
                                    When(
                                        name=permissions_group_name_for_role(
                                            role, website
                                        ),
                                        then=Value(role),
                                    )
                                    for role in constants.ROLE_GROUP_MAPPING
                                ]
                            ),
                            output_field=CharField(),
                        )
                    )
                    .values("role_name")[:1],
                    output_field=CharField(),
                )
            )
            .order_by("name", "id")
            .distinct()
        )

    def get_serializer_context(self):
        """ Get the serializer context """
        return {
            "website": self.website,
        }

    def destroy(self, request, *args, **kwargs):
        """ Remove the user from all groups for this website """
        user = self.get_object()
        user.groups.remove(*get_groups_with_perms(self.website))
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebsiteContentViewSet(
    NestedViewSetMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Viewset for WebsiteContent"""

    permission_classes = (HasWebsiteContentPermission,)
    pagination_class = DefaultPagination
    lookup_field = "text_id"

    def get_queryset(self):
        parent_lookup_website = self.kwargs.get("parent_lookup_website")
        filter_type = self.request.query_params.get("type")

        queryset = WebsiteContent.objects.filter(website__name=parent_lookup_website)
        if filter_type:
            queryset = queryset.filter(type=filter_type)
        return queryset.order_by("-updated_on")

    def get_serializer_class(self):
        if self.action == "list":
            return WebsiteContentSerializer
        elif self.action == "create":
            return WebsiteContentCreateSerializer
        else:
            return WebsiteContentDetailSerializer

    def get_serializer_context(self):
        if self.action != "create":
            return super().get_serializer_context()

        parent_lookup_website = self.kwargs.get("parent_lookup_website")
        website_qset = Website.objects.values("pk", "starter__config").get(
            name=parent_lookup_website
        )
        added_context = {"website_pk": website_qset["pk"]}
        site_config = website_qset["starter__config"] or {}
        content_type = self.request.data.get("type")
        config_item = (
            find_config_item(site_config, content_type)
            if content_type is not None
            else None
        )
        if site_config and config_item is not None:
            added_context["is_page_content"] = is_page_content(site_config, config_item)
        return {**super().get_serializer_context(), **added_context}
