""" Views for websites """
from django.contrib.auth.models import Group
from django.db.models import CharField, OuterRef, Q, Subquery, Value
from django.utils.text import slugify
from guardian.shortcuts import (
    get_groups_with_perms,
    get_objects_for_user,
    get_users_with_perms,
)
from mitol.common.utils.datetime import now_in_utc
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
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
    permissions_group_for_role,
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
    lookup_field = "id"
    lookup_url_kwarg = "user_id"

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
        owner_user_id = website.owner.id if website.owner else None

        # Return the individual user and group if a primary key is provided
        user_id = self.kwargs.get("user_id", None)
        if user_id:
            try:
                user_id = int(user_id)
            except ValueError:
                raise ValidationError(  # pylint: disable=raise-missing-from
                    {"errors": ["Invalid user"]}
                )

            if user_id == owner_user_id:
                return User.objects.filter(id=user_id).annotate(
                    group=Value(constants.ROLE_OWNER, CharField())
                )
            group_subquery = Group.objects.filter(
                Q(user__id=OuterRef("id")) & Q(name__in=website_groups)
            )
            return User.objects.filter(
                Q(id=user_id) & Q(groups__name__in=website_groups)
            ).annotate(group=Subquery(group_subquery.values("name")[:1]))

        # Otherwise get all the collaborators and annotate with the relevant group they are in
        query = User.objects.filter(id=owner_user_id).annotate(
            group=Value(constants.ROLE_OWNER, CharField())
        )
        for group_name in website_groups:
            query = query.union(
                Group.objects.get(name=group_name)
                .user_set.exclude(id=owner_user_id)
                .annotate(group=Value(group_name, CharField()))
            )
        return query.order_by("name", "id")

    def destroy(self, request, *args, **kwargs):
        """Remove the user from all groups for this website"""
        instance = self.get_object()
        website = Website.objects.get(name=self.kwargs.get("parent_lookup_website"))
        for group in get_groups_with_perms(website):
            instance.groups.remove(group)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        """ Add a user to the website as a collaborator"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        website = Website.objects.get(name=self.kwargs.get("parent_lookup_website"))
        group_name = permissions_group_for_role(
            serializer.validated_data.get("role"), website
        )
        user = User.objects.get(email=serializer.data.get("email"))
        if user in get_users_with_perms(website) or user == website.owner:
            raise ValidationError(
                {"errors": ["User is already a collaborator for this site"]}
            )
        user.groups.add(Group.objects.get(name=group_name))
        serializer.validated_data.update(
            {"user_id": user.id, "name": user.name, "group": group_name}
        )
        return Response(serializer.validated_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """ Change a collaborator's permission group for the website """
        partial = kwargs.pop("partial", False)
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        website = Website.objects.get(name=self.kwargs.get("parent_lookup_website"))
        group_name = permissions_group_for_role(
            serializer.validated_data.get("role"), website
        )

        # User should only belong to one group per website
        for group in get_groups_with_perms(website):
            if group_name and group.name == group_name:
                user.groups.add(group)
            else:
                user.groups.remove(group)
        return Response(
            {"role": serializer.validated_data["role"], "group": group_name}
        )


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
    lookup_field = "uuid"

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
