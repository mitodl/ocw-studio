"""Views for websites"""
import json
import logging
import os

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db.models import Case, CharField, F, OuterRef, Q, Value, When
from django.utils.functional import cached_property
from django.utils.text import slugify
from guardian.shortcuts import get_groups_with_perms, get_objects_for_user
from mitol.common.utils.datetime import now_in_utc
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from content_sync.api import (
    sync_github_website_starters,
    trigger_publish,
    trigger_unpublished_removal,
    update_website_backend,
)
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from gdrive_sync.constants import WebsiteSyncStatus
from gdrive_sync.tasks import import_website_files
from main import features
from main.permissions import ReadonlyPermission
from main.utils import is_dev, uuid_string, valid_key
from main.views import DefaultPagination
from users.models import User
from websites import constants
from websites.api import get_valid_new_filename, update_website_status
from websites.constants import (
    CONTENT_TYPE_COURSE_LIST,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE_COLLECTION,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_SUCCEEDED,
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_OTHER,
    RESOURCE_TYPE_VIDEO,
    WebsiteStarterStatus,
)
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.permissions import (
    BearerTokenPermission,
    HasWebsiteCollaborationPermission,
    HasWebsiteContentPermission,
    HasWebsitePermission,
    HasWebsitePreviewPermission,
    HasWebsitePublishPermission,
    is_global_admin,
)
from websites.serializers import (
    WebsiteBasicSerializer,
    WebsiteCollaboratorSerializer,
    WebsiteContentCreateSerializer,
    WebsiteContentDetailSerializer,
    WebsiteContentSerializer,
    WebsiteDetailSerializer,
    WebsiteMassBuildSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
    WebsiteStatusSerializer,
    WebsiteUnpublishSerializer,
    WebsiteUrlSerializer,
    WebsiteWriteSerializer,
)
from websites.site_config_api import SiteConfig
from websites.utils import get_valid_base_filename, permissions_group_name_for_role

log = logging.getLogger(__name__)

test_site_filter = Q(
    name__in=[settings.OCW_WWW_TEST_SLUG, settings.OCW_COURSE_TEST_SLUG]
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
        published = self.request.query_params.get("published", None)

        user = self.request.user
        published_filter = Q(
            first_published_to_production__isnull=False,
            first_published_to_production__lte=now_in_utc(),
            publish_date__isnull=False,
            unpublish_status__isnull=True,
            websitecontent__type=CONTENT_TYPE_METADATA,
            websitecontent__metadata__isnull=False,
        )
        if self.request.user.is_anonymous:
            # Anonymous users should get a list of all published websites (used for ocw-www carousel)  # noqa: E501
            ordering = "-first_published_to_production"
            queryset = Website.objects.filter(published_filter).distinct()
        elif is_global_admin(user):
            # Global admins should get a list of all websites, published or not.
            queryset = Website.objects.all()
        else:
            # Other authenticated users should get a list of websites they are editors/admins/owners for.  # noqa: E501
            queryset = get_objects_for_user(user, constants.PERMISSION_VIEW)

        if search is not None and search != "":
            # search query param is used in react-select typeahead, and should
            # match on the title, name, and short_id
            search_filter = Q(search=SearchQuery(search)) | Q(search__icontains=search)
            if "." in search:
                # postgres text search behaves oddly with periods but not dashes
                search_filter = search_filter | Q(
                    search=SearchQuery(search.replace(".", "-"))
                )
            queryset = queryset.annotate(
                search=SearchVector(
                    "name",
                    "title",
                    "short_id",
                )
            ).filter(search_filter)

        if resourcetype is not None:
            queryset = queryset.filter(metadata__resourcetype=resourcetype)

        if website_type is not None:
            queryset = queryset.filter(starter__slug=website_type)

        if published is not None:
            published = _parse_bool(published)
            if published:
                queryset = queryset.filter(published_filter)
            else:
                queryset = queryset.exclude(published_filter)

        if not is_dev():
            queryset = queryset.exclude(test_site_filter)

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
        elif self.action in ("preview", "publish"):
            return WebsiteUrlSerializer
        else:
            return WebsiteDetailSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs["context"] = self.get_serializer_context()

        # If a new website is being created, and the request includes a title but not a name, auto-generate the  # noqa: E501
        # name by slugify-ing the title before passing the data off to the serializer.
        if (
            self.request.method == "POST"
            and "name" not in self.request.data
            and self.request.data.get("title")
        ):
            request_data = self.request.data.copy()
            request_data["name"] = slugify(request_data["title"], allow_unicode=True)
            kwargs["data"] = request_data

        return serializer_class(*args, **kwargs)

    def publish_version(self, name, version, request):
        """Process a publish request for the specified version"""
        try:
            website = self.get_object()
            if website.publish_date is None:
                if not request.data.get("url_path"):
                    request.data["url_path"] = None
                serializer = WebsiteUrlSerializer(data=request.data, instance=website)
                if serializer.is_valid(raise_exception=True):
                    serializer.update(website, serializer.validated_data)
            if version == VERSION_DRAFT:
                Website.objects.filter(pk=website.pk).update(
                    has_unpublished_draft=False,
                    draft_publish_status=constants.PUBLISH_STATUS_NOT_STARTED,
                    draft_publish_status_updated_on=now_in_utc(),
                    latest_build_id_draft=None,
                    draft_last_published_by=request.user,
                )
            else:
                Website.objects.filter(pk=website.pk).update(
                    has_unpublished_live=False,
                    live_publish_status=constants.PUBLISH_STATUS_NOT_STARTED,
                    live_publish_status_updated_on=now_in_utc(),
                    latest_build_id_live=None,
                    live_last_published_by=request.user,
                    unpublish_status=None,
                    last_unpublished_by=None,
                )
            trigger_publish(website.name, version)
            return Response(status=200)
        except ValidationError as ve:
            return Response(data=ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Error publishing %s version for %s", version, name)
            return Response(status=500, data={"details": str(exc)})

    @action(
        detail=True, methods=["post"], permission_classes=[HasWebsitePreviewPermission]
    )
    def preview(self, request, name=None):
        """Trigger a preview task for the website"""
        return self.publish_version(name, VERSION_DRAFT, request)

    @action(
        detail=True, methods=["post"], permission_classes=[HasWebsitePublishPermission]
    )
    def publish(self, request, name=None):
        """Trigger a publish task for the website"""
        return self.publish_version(name, VERSION_LIVE, request)

    @action(
        detail=True,
        methods=["post", "get"],
        permission_classes=[HasWebsitePublishPermission],
    )
    def unpublish(self, request, name=None):
        """Unpublish the site and trigger the remove-unpublished-sites pipeline"""
        try:
            website = self.get_object()
            if request.method == "GET":
                ocw_www_dependencies = WebsiteContent.objects.filter(
                    (
                        Q(type=CONTENT_TYPE_COURSE_LIST)
                        | Q(type=CONTENT_TYPE_RESOURCE_COLLECTION)
                    ),
                    (
                        Q(metadata__courses__icontains=website.name)
                        | Q(metadata__resources__content__icontains=website.name)
                    ),
                    website__name=settings.ROOT_WEBSITE_NAME,
                )
                course_content_dependencies = WebsiteContent.objects.filter(
                    ~Q(website__name=website.name),
                    type=CONTENT_TYPE_PAGE,
                    markdown__icontains=website.name,
                )
                course_dependencies = Website.objects.filter(
                    ~Q(name=website.name), metadata__icontains=website.name
                )
                return Response(
                    status=200,
                    data={
                        "site_dependencies": {
                            "ocw_www": WebsiteContentSerializer(
                                instance=ocw_www_dependencies, many=True
                            ).data,
                            "course": WebsiteBasicSerializer(
                                instance=course_dependencies, many=True
                            ).data,
                            "course_content": WebsiteContentSerializer(
                                instance=course_content_dependencies, many=True
                            ).data,
                        }
                    },
                )
            else:
                Website.objects.filter(pk=website.pk).update(
                    unpublish_status=PUBLISH_STATUS_NOT_STARTED,
                    last_unpublished_by=request.user,
                )
                trigger_unpublished_removal(website)
                return Response(
                    status=200,
                    data="The site has been submitted for unpublishing.",
                )
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Error unpublishing %s", name)
            return Response(status=500, data={"details": str(exc)})

    @action(detail=True, methods=["post"], permission_classes=[BearerTokenPermission])
    def pipeline_status(self, request, name=None):
        """Process webhook requests from concourse pipeline runs"""
        website = get_object_or_404(Website, name=name)
        data = request.data
        version = data["version"]
        publish_status = data.get("status")
        unpublished = data.get("unpublished", False) and version == VERSION_LIVE
        update_website_status(
            website, version, publish_status, now_in_utc(), unpublished=unpublished
        )
        return Response(status=200)


class WebsiteMassBuildViewSet(viewsets.ViewSet):
    """Return a list of previously published sites, with the info required by the mass-build-sites pipeline"""  # noqa: E501

    serializer_class = WebsiteMassBuildSerializer
    permission_classes = (BearerTokenPermission,)

    def list(self, request):  # noqa: A003, ARG002
        """Return a list of websites that have been previously published, per version"""
        version = self.request.query_params.get("version")
        starter = self.request.query_params.get("starter")
        if version not in (VERSION_LIVE, VERSION_DRAFT):
            msg = "Invalid version"
            raise ValidationError(msg)
        publish_date_field = (
            "publish_date" if version == VERSION_LIVE else "draft_publish_date"
        )

        # Get all sites, minus any sites that have never been successfully published
        sites = Website.objects.exclude(
            Q(**{f"{publish_date_field}__isnull": True}) | Q(url_path__isnull=True)
        )
        # For live builds, exclude previously published sites that have been unpublished
        if version == VERSION_LIVE:
            sites = sites.exclude(unpublish_status__isnull=False)
        # If a starter has been specified by the query, only return sites made with that starter  # noqa: E501
        if starter:
            sites = sites.filter(starter=WebsiteStarter.objects.get(slug=starter))
        sites = sites.prefetch_related("starter").order_by("name")
        if not is_dev():
            sites = sites.exclude(test_site_filter)
        serializer = WebsiteMassBuildSerializer(instance=sites, many=True)
        return Response({"sites": serializer.data})


class WebsiteUnpublishViewSet(viewsets.ViewSet):
    """
    Return a list of sites that need to be unpublished, with the info required by the remove-unpublished-sites pipeline
    """  # noqa: E501

    permission_classes = (BearerTokenPermission,)

    def list(self, request):  # noqa: A003, ARG002
        """Return a list of websites that need to be processed by the remove-unpublished-sites pipeline"""  # noqa: E501
        sites = (
            Website.objects.exclude(
                Q(unpublish_status=PUBLISH_STATUS_SUCCEEDED)
                | Q(unpublish_status__isnull=True)
            )
            .prefetch_related("starter")
            .order_by("name")
        )
        if not is_dev():
            sites = sites.exclude(test_site_filter)
        serializer = WebsiteUnpublishSerializer(instance=sites, many=True)
        return Response({"sites": serializer.data})


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
        queryset = WebsiteStarter.objects.filter(
            status__in=WebsiteStarterStatus.ALLOWED_STATUSES
        ).all()
        if features.is_enabled(features.USE_LOCAL_STARTERS):
            return queryset
        else:
            return queryset.filter(source=constants.STARTER_SOURCE_GITHUB)

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
                    if os.path.basename(file)  # noqa: PTH119
                    == settings.OCW_STUDIO_SITE_CONFIG_FILE  # noqa: PTH119, RUF100
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
    """Viewset for Website collaborators along with their group/role"""

    serializer_class = WebsiteCollaboratorSerializer
    permission_classes = (HasWebsiteCollaborationPermission,)
    pagination_class = DefaultPagination
    lookup_url_kwarg = "user_id"

    @cached_property
    def website(self):
        """Fetches the Website for this request"""  # noqa: D401
        return get_object_or_404(Website, name=self.kwargs.get("parent_lookup_website"))

    def get_queryset(self):
        """
        Builds a queryset of relevant users with permissions for this website, and annotates them by group name/role
        (owner, administrator, editor, or global administrator)
        """  # noqa: E501, D401
        website = self.website
        website_group_names = [
            *list(get_groups_with_perms(website).values_list("name", flat=True)),
            constants.GLOBAL_ADMIN,
        ]
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
        """Get the serializer context"""
        return {
            "website": self.website,
        }

    def destroy(self, request, *args, **kwargs):  # noqa: ARG002
        """Remove the user from all groups for this website"""
        user = self.get_object()
        user.groups.remove(*get_groups_with_perms(self.website))
        return Response(status=status.HTTP_204_NO_CONTENT)


def _get_derived_website_content_data(
    request_data: dict, site_config: SiteConfig, website_pk: str
) -> dict:
    """Derives values that should be added to the request data if a WebsiteContent object is being created"""  # noqa: E501, D401
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
            filename_base=slugify(
                get_valid_base_filename(slug, content_type), allow_unicode=True
            ),
        )
    return added_data


def _get_value_list_from_query_params(query_params, key):
    """
    Get a list of values which have keys that start with key[ or key
    """
    filter_type_keys = [
        qs_key
        for qs_key in query_params
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
        published = self.request.query_params.get("published", None)

        queryset = WebsiteContent.objects.filter(
            website__name=parent_lookup_website
        ).select_related("website", "website__starter")
        if types:
            queryset = queryset.filter(type__in=types)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(file__iregex=f"{search}([^/]+$|$)")
            )
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
        if published:
            published = _parse_bool(published)
            if published is True:
                queryset = queryset.filter(
                    website__publish_date__isnull=False,
                    # if the associated website has been published after
                    # the content record was created, then it has been published
                    # at least once
                    website__publish_date__gt=F("created_on"),
                )
            else:
                # unpublished content is any content where the associated
                # website has never been published or where the website was
                # most recently published before it was created
                queryset = queryset.filter(
                    Q(website__publish_date__isnull=True)
                    | Q(website__publish_date__lt=F("created_on"))
                )
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
        """(soft) deletes a WebsiteContent record"""
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
    def gdrive_sync(
        self, request, **kwargs  # noqa: ARG002
    ):  # pylint:disable=unused-argument
        """Trigger a task to sync all non-video Google Drive files"""
        website = Website.objects.get(name=self.kwargs.get("parent_lookup_website"))
        website.sync_status = WebsiteSyncStatus.PENDING
        website.save()
        import_website_files.delay(website.name)
        return Response(status=200)
