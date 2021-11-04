""" Views for websites """
import json
import logging
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import Case, CharField, OuterRef, Q, Value, When
from django.utils.functional import cached_property
from django.utils.text import slugify
from guardian.shortcuts import get_groups_with_perms, get_objects_for_user
from mitol.common.utils.datetime import now_in_utc
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from content_sync.api import (
    preview_website,
    publish_website,
    sync_github_website_starters,
    update_website_backend,
)
from content_sync.tasks import poll_build_status_until_complete
from gdrive_sync.constants import WebsiteSyncStatus
from gdrive_sync.tasks import import_website_files
from main import features
from main.permissions import ReadonlyPermission
from main.utils import uuid_string, valid_key
from main.views import DefaultPagination
from users.models import User
from websites import constants
from websites.api import (
    get_valid_new_filename,
    mail_website_admins_on_publish,
    unassigned_youtube_ids,
)
from websites.constants import (
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_OTHER,
    RESOURCE_TYPE_VIDEO,
)
from websites.models import (
    Website,
    WebsiteCollection,
    WebsiteCollectionItem,
    WebsiteContent,
    WebsiteStarter,
)
from websites.permissions import (
    BearerTokenPermission,
    HasWebsiteCollaborationPermission,
    HasWebsiteCollectionItemPermission,
    HasWebsiteCollectionPermission,
    HasWebsiteContentPermission,
    HasWebsitePermission,
    HasWebsitePreviewPermission,
    HasWebsitePublishPermission,
    is_global_admin,
)
from websites.serializers import (
    WebsiteCollaboratorSerializer,
    WebsiteCollectionItemSerializer,
    WebsiteCollectionSerializer,
    WebsiteContentCreateSerializer,
    WebsiteContentDetailSerializer,
    WebsiteContentSerializer,
    WebsiteDetailSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
    WebsiteStatusSerializer,
    WebsiteWriteSerializer,
)
from websites.site_config_api import SiteConfig
from websites.utils import permissions_group_name_for_role


log = logging.getLogger(__name__)


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

    pagination_class = DefaultPagination
    permission_classes = (HasWebsitePermission,)
    lookup_field = "name"

    def get_queryset(self):
        """
        Generate a QuerySet for fetching websites.
        """
        ordering = self.request.query_params.get("sort", "-updated_on")
        website_type = self.request.query_params.get("type", None)
        search = self.request.query_params.get("search", None)
        resourcetype = self.request.query_params.get("resourcetype", None)

        user = self.request.user
        if self.request.user.is_anonymous:
            # Anonymous users should get a list of all published websites (used for ocw-www carousel)
            ordering = "-publish_date"
            queryset = Website.objects.filter(
                publish_date__lte=now_in_utc(),
                # Replace this after imported ocw sites have metadata stored in WebsiteContent objects
                metadata__isnull=False,
            )
        elif is_global_admin(user):
            # Global admins should get a list of all websites, published or not.
            queryset = Website.objects.all()
        else:
            # Other authenticated users should get a list of websites they are editors/admins/owners for.
            queryset = get_objects_for_user(user, constants.PERMISSION_VIEW)

        if search is not None:
            # search query param is used in react-select typeahead, and should match on the title
            queryset = queryset.filter(title__icontains=search)

        if resourcetype is not None:
            queryset = queryset.filter(metadata__resourcetype=resourcetype)

        if website_type is not None:
            queryset = queryset.filter(starter__slug=website_type)
        return queryset.select_related("starter").order_by(ordering)

    def get_serializer_class(self):
        if self.action == "list":
            return WebsiteSerializer
        elif self.action == "create":
            return WebsiteWriteSerializer
        elif self.action == "retrieve" and _parse_bool(
            self.request.query_params.get("only_status")
        ):
            return WebsiteStatusSerializer
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

    @action(
        detail=True, methods=["post"], permission_classes=[HasWebsitePreviewPermission]
    )
    def preview(self, request, name=None):
        """Trigger a preview task for the website"""
        try:
            website = self.get_object()
            incomplete_videos = [
                video.title for video in unassigned_youtube_ids(website)
            ]
            message = ""
            if len(incomplete_videos) > 0:
                message = f"WARNING: The following videos have missing YouTube IDs: {','.join(incomplete_videos)}"
            preview_website(website)
            website.has_unpublished_draft = False
            website.draft_publish_status = constants.PUBLISH_STATUS_NOT_STARTED
            website.draft_publish_status_updated_on = now_in_utc()
            website.save()
            poll_build_status_until_complete.delay(
                website.name,
                "draft",
                (
                    timedelta(seconds=settings.MAX_WEBSITE_POLL_SECONDS) + now_in_utc()
                ).isoformat(),
            )
            return Response(
                status=200,
                data={"details": message},
            )
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Error previewing %s", name)
            return Response(status=500, data={"details": str(exc)})

    @action(
        detail=True, methods=["post"], permission_classes=[HasWebsitePublishPermission]
    )
    def publish(self, request, name=None):
        """Trigger a publish task for the website"""
        try:
            website = self.get_object()
            incomplete_videos = [
                video.title for video in unassigned_youtube_ids(website)
            ]
            if len(incomplete_videos) > 0:
                return Response(
                    status=400,
                    data={
                        "details": f"The following video resources require YouTube ID's: {','.join(incomplete_videos)}"
                    },
                )
            publish_website(website)
            website.has_unpublished_live = False
            website.live_publish_status = constants.PUBLISH_STATUS_NOT_STARTED
            website.live_publish_status_updated_on = now_in_utc()
            website.save()
            poll_build_status_until_complete.delay(
                website.name,
                "live",
                (
                    timedelta(seconds=settings.MAX_WEBSITE_POLL_SECONDS) + now_in_utc()
                ).isoformat(),
            )
            return Response(
                status=200,
                data={"details": ""},
            )
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Error publishing %s", name)
            return Response(status=500, data={"details": str(exc)})

    @action(detail=True, methods=["post"], permission_classes=[BearerTokenPermission])
    def pipeline_complete(self, request, name=None):
        """Process webhook requests from completed preview/publish pipeline runs"""
        data = request.data
        version = data["version"]
        # success value will come back as a string
        succeeded = data.get("success", "false").lower() == "true"
        mail_website_admins_on_publish(
            Website.objects.get(name=name), version, succeeded
        )
        return Response(status=200)


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

    @action(detail=False, methods=["post"], permission_classes=[])
    def site_configs(self, request):
        """Process webhook requests for WebsiteStarter site configs"""
        data = json.loads(request.body)
        if data.get("repository"):
            try:
                if not valid_key(settings.GITHUB_WEBHOOK_KEY, request):
                    return Response(status=status.HTTP_403_FORBIDDEN)
                files = [
                    file
                    for sublist in [
                        commit["modified"] + commit["added"]
                        for commit in data["commits"]
                    ]
                    for file in sublist
                    if os.path.basename(file) == settings.OCW_STUDIO_SITE_CONFIG_FILE
                ]
                sync_github_website_starters(
                    data["repository"]["html_url"], files, commit=data.get("after")
                )
            except Exception as exc:  # pylint: disable=broad-except
                log.exception("Error syncing config files")
                return Response(status=500, data={"details": str(exc)})
            return Response(status=status.HTTP_202_ACCEPTED)
        else:
            # Only github webhooks are currently supported
            return Response(status=status.HTTP_400_BAD_REQUEST)


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


def _get_derived_website_content_data(
    request_data: dict, site_config: SiteConfig, website_pk: str
) -> dict:
    """Derives values that should be added to the request data if a WebsiteContent object is being created"""
    added_data = {}
    if "text_id" not in request_data:
        added_data["text_id"] = uuid_string()
    content_type = request_data.get("type")
    config_item = (
        site_config.find_item_by_name(name=content_type)
        if content_type is not None
        else None
    )
    is_page_content = False
    if site_config and config_item is not None:
        is_page_content = site_config.is_page_content(config_item)
        added_data["is_page_content"] = is_page_content
    dirpath = request_data.get("dirpath")
    if dirpath is None and config_item is not None and is_page_content:
        dirpath = config_item.file_target
        added_data["dirpath"] = dirpath
    slug_key = config_item.item.get("slug") if config_item is not None else None
    if not slug_key:
        slug_key = "title"
    slug = (
        added_data.get(slug_key)
        or request_data.get(slug_key)
        or request_data.get("metadata", {}).get(slug_key)
    )
    if slug is not None:
        added_data["filename"] = get_valid_new_filename(
            website_pk=website_pk,
            dirpath=dirpath,
            filename_base=slugify(slug),
        )
    return added_data


def _get_value_list_from_query_params(query_params, key):
    """
    Get a list of values which have keys that start with key[ or key
    """
    filter_type_keys = [
        qs_key
        for qs_key in query_params.keys()
        # View should accept "type" as a single query param, or multiple types,
        # e.g.: "?type[0]=sometype&type[1]=othertype"
        if qs_key == key or qs_key.startswith(f"{key}[")
    ]
    return [query_params[_key] for _key in filter_type_keys]


def _parse_bool(value):
    """
    Parse a query string value into a bool
    """
    return value and value.lower() != "false"


class WebsiteContentViewSet(
    NestedViewSetMixin,
    viewsets.ModelViewSet,
):
    """Viewset for WebsiteContent"""

    permission_classes = (HasWebsiteContentPermission,)
    pagination_class = DefaultPagination
    lookup_field = "text_id"

    def get_queryset(self):
        parent_lookup_website = self.kwargs.get("parent_lookup_website")
        search = self.request.query_params.get("search")
        resourcetype = self.request.query_params.get("resourcetype")
        types = _get_value_list_from_query_params(self.request.query_params, "type")

        queryset = WebsiteContent.objects.filter(
            website__name=parent_lookup_website
        ).select_related("website", "website__starter")
        if types:
            queryset = queryset.filter(type__in=types)
        if search:
            queryset = queryset.filter(title__icontains=search)
        if resourcetype:
            if resourcetype == RESOURCE_TYPE_OTHER:
                queryset = queryset.exclude(
                    metadata__resourcetype__in=[
                        RESOURCE_TYPE_IMAGE,
                        RESOURCE_TYPE_DOCUMENT,
                        RESOURCE_TYPE_VIDEO,
                    ]
                )
            else:
                queryset = queryset.filter(metadata__resourcetype=resourcetype)

        if "page_content" in self.request.query_params:
            queryset = queryset.filter(
                is_page_content=(_parse_bool(self.request.query_params["page_content"]))
            )
        return queryset.order_by("-updated_on")

    def get_serializer_class(self):
        detailed_list = self.request.query_params.get("detailed_list", False)
        if self.action == "list" and detailed_list:
            return WebsiteContentDetailSerializer
        elif self.action == "list":
            return WebsiteContentSerializer
        elif self.action == "create":
            return WebsiteContentCreateSerializer
        else:
            return WebsiteContentDetailSerializer

    def get_serializer_context(self):
        if self.action != "create":
            return {
                **super().get_serializer_context(),
                "content_context": _parse_bool(
                    self.request.query_params.get("content_context")
                ),
            }

        parent_lookup_website = self.kwargs.get("parent_lookup_website")
        website_qset = Website.objects.values("pk", "starter__config").get(
            name=parent_lookup_website
        )
        website_pk = website_qset["pk"]
        added_context = {"website_id": website_pk}
        raw_site_config = website_qset["starter__config"] or {}
        site_config = SiteConfig(raw_site_config)
        added_context.update(
            _get_derived_website_content_data(
                request_data=self.request.data,
                site_config=site_config,
                website_pk=website_pk,
            )
        )
        return {**super().get_serializer_context(), **added_context}

    def perform_destroy(self, instance: WebsiteContent):
        """ (soft) deletes a WebsiteContent record """
        instance.updated_by = self.request.user
        super().perform_destroy(
            instance
        )  # this actually performs a save() because it's a soft delete
        update_website_backend(instance.website)
        return instance

    @action(
        detail=False,
        methods=["post"],
        permission_classes=(HasWebsiteContentPermission,),
    )
    def gdrive_sync(self, request, **kwargs):  # pylint:disable=unused-argument
        """ Trigger a task to sync all non-video Google Drive files"""
        website = Website.objects.get(name=self.kwargs.get("parent_lookup_website"))
        website.sync_status = WebsiteSyncStatus.PENDING
        website.save()
        import_website_files.delay(website.name)
        return Response(status=200)


class WebsiteCollectionViewSet(
    viewsets.ModelViewSet,
):
    """Viewset for WebsiteCollections"""

    permission_classes = (HasWebsiteCollectionPermission,)
    pagination_class = DefaultPagination
    serializer_class = WebsiteCollectionSerializer
    lookup_field = "id"

    def get_queryset(self):
        return WebsiteCollection.objects.all()


class WebsiteCollectionItemViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """Viewset for WebsiteCollectionItems"""

    permission_classes = (HasWebsiteCollectionItemPermission,)
    serializer_class = WebsiteCollectionItemSerializer

    def get_serializer_context(self):
        added_context = {
            "website_collection_id": self.kwargs.get("parent_lookup_collection")
        }
        return {**super().get_serializer_context(), **added_context}

    def get_queryset(self):
        parent_lookup_collection = self.kwargs.get("parent_lookup_collection")
        queryset = WebsiteCollectionItem.objects.filter(
            website_collection__id=parent_lookup_collection
        ).select_related("website")
        return queryset.order_by("position")
