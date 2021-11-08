""" Serializers for websites """
import logging
from collections import defaultdict
from urllib.parse import urljoin

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import F, Max
from guardian.shortcuts import get_groups_with_perms, get_users_with_perms
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from content_sync.api import (
    create_website_backend,
    create_website_publishing_pipeline,
    update_website_backend,
)
from gdrive_sync.api import gdrive_root_url, is_gdrive_enabled
from gdrive_sync.tasks import create_gdrive_folders
from main.serializers import RequestUserSerializerMixin
from users.models import User
from websites import constants
from websites.api import detect_mime_type, update_youtube_thumbnail
from websites.models import (
    Website,
    WebsiteCollection,
    WebsiteCollectionItem,
    WebsiteContent,
    WebsiteStarter,
)
from websites.permissions import is_global_admin, is_site_admin
from websites.site_config_api import SiteConfig
from websites.utils import permissions_group_name_for_role


log = logging.getLogger(__name__)


ROLE_ERROR_MESSAGES = {"invalid_choice": "Invalid role", "required": "Role is required"}


class WebsiteStarterSerializer(serializers.ModelSerializer):
    """ Serializer for website starters """

    class Meta:
        model = WebsiteStarter
        fields = ["id", "name", "path", "source", "commit", "slug"]


class WebsiteStarterDetailSerializer(serializers.ModelSerializer):
    """ Serializer for website starters with serialized config """

    class Meta:
        model = WebsiteStarter
        fields = WebsiteStarterSerializer.Meta.fields + ["config"]


class WebsiteGoogleDriveMixin(serializers.Serializer):
    """ Serializer for website google drive details"""

    gdrive_url = serializers.SerializerMethodField()

    def get_gdrive_url(self, instance):
        """ Get the Google Drive folder URL for the site"""
        if is_gdrive_enabled() and instance.gdrive_folder:
            return urljoin(gdrive_root_url(), instance.gdrive_folder)
        return None


class WebsiteSerializer(serializers.ModelSerializer):
    """ Serializer for websites """

    starter = WebsiteStarterSerializer(read_only=True)

    class Meta:
        model = Website
        fields = [
            "uuid",
            "created_on",
            "updated_on",
            "name",
            "short_id",
            "title",
            "source",
            "draft_publish_date",
            "publish_date",
            "metadata",
            "starter",
            "owner",
        ]
        extra_kwargs = {"owner": {"write_only": True}}


class WebsiteDetailSerializer(
    serializers.ModelSerializer, WebsiteGoogleDriveMixin, RequestUserSerializerMixin
):
    """ Serializer for websites with serialized config """

    starter = WebsiteStarterDetailSerializer(read_only=True)
    is_admin = serializers.SerializerMethodField(read_only=True)
    live_url = serializers.SerializerMethodField()
    draft_url = serializers.SerializerMethodField()

    def get_is_admin(self, obj):
        """ Determine if the request user is an admin"""
        user = self.user_from_request()
        if user:
            return is_site_admin(user, obj)
        return False

    def get_live_url(self, instance):
        """Get the live url for the site"""
        return instance.get_url(version="live")

    def get_draft_url(self, instance):
        """Get the draft url for the site"""
        return instance.get_url(version="draft")

    def update(self, instance, validated_data):
        """ Remove owner attribute if present, it should not be changed"""
        validated_data.pop("owner", None)
        with transaction.atomic():
            website = super().update(instance, validated_data)
        update_website_backend(website)
        return website

    class Meta:
        model = Website
        fields = WebsiteSerializer.Meta.fields + [
            "is_admin",
            "draft_url",
            "live_url",
            "has_unpublished_live",
            "has_unpublished_draft",
            "gdrive_url",
            "live_publish_status",
            "live_publish_status_updated_on",
            "draft_publish_status",
            "draft_publish_status_updated_on",
            "gdrive_url",
            "sync_status",
            "sync_errors",
            "synced_on",
        ]
        read_only_fields = [
            "uuid",
            "created_on",
            "updated_on",
            "starter",
            "owner",
            "has_unpublished_live",
            "has_unpublished_draft",
            "publish_date",
            "draft_publish_date",
            "live_publish_status",
            "live_publish_status_updated_on",
            "draft_publish_status",
            "draft_publish_status_updated_on",
            "gdrive_url",
            "sync_status",
            "sync_errors",
            "synced_on",
        ]


class WebsiteStatusSerializer(serializers.ModelSerializer, WebsiteGoogleDriveMixin):
    """Serializer for website status fields"""

    class Meta:
        model = Website
        fields = [
            "uuid",
            "name",
            "publish_date",
            "draft_publish_date",
            "has_unpublished_live",
            "has_unpublished_draft",
            "live_publish_status",
            "live_publish_status_updated_on",
            "draft_publish_status",
            "draft_publish_status_updated_on",
            "gdrive_url",
            "sync_status",
            "sync_errors",
            "synced_on",
        ]
        read_only_fields = fields


class WebsiteWriteSerializer(serializers.ModelSerializer, RequestUserSerializerMixin):
    """
    Deserializer for websites
    NOTE: This is needed because DRF does not directly support saving a related field using just an id. We want to
    deserialize and save Website objects and save the related WebsiteStarter as an id, but there is no clean way to
    do that with DRF, hence this added serializer class.
    """

    starter = serializers.PrimaryKeyRelatedField(
        queryset=WebsiteStarter.objects.all(), write_only=True
    )

    def create(self, validated_data):
        """Ensure that the website is created by the requesting user"""
        validated_data["owner"] = self.user_from_request()
        with transaction.atomic():
            website = super().create(validated_data)
        create_website_backend(website)
        create_website_publishing_pipeline(website)
        create_gdrive_folders.delay(website.short_id)
        return website

    class Meta:
        model = Website
        fields = WebsiteSerializer.Meta.fields
        read_only_fields = [
            "has_unpublished_live",
            "has_unpublished_draft",
            "publish_date",
            "draft_publish_date",
            "live_publish_status",
            "live_publish_status_updated_on",
            "draft_publish_status",
            "draft_publish_status_updated_on",
        ]


class WebsiteCollaboratorSerializer(serializers.Serializer):
    """A non-model serializer for updating the permissions (by group) that a user has for a Website."""

    role = serializers.ChoiceField(
        choices=constants.GROUP_ROLES, error_messages=ROLE_ERROR_MESSAGES
    )
    email = serializers.EmailField(allow_null=True, required=False)
    group = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(read_only=True, source="id")

    @property
    def website(self):
        """Get the website"""
        return self.context["website"]

    def validate_email(self, email):
        """ The user should exist and not be a global admin """
        user = User.objects.filter(email=email).first()
        if not user:
            raise ValidationError("User does not exist")
        if is_global_admin(user):
            raise ValidationError("User is a global admin")
        return email

    def validate(self, attrs):
        """Make sure all required attributes are present for post/patch"""
        if not attrs.get("role"):
            raise ValidationError({"role": "Role is required"})
        if not self.instance and not attrs.get("email"):
            raise ValidationError({"email": "Email is required"})
        return attrs

    def create(self, validated_data):
        """Creating a contributor adds the user to the group corresponding to the specified role"""
        website = self.website
        role = validated_data.get("role")
        user = User.objects.get(email=validated_data.get("email"))
        group_name = permissions_group_name_for_role(role, website)
        if user in get_users_with_perms(website) or user == website.owner:
            raise ValidationError(
                {"email": ["User is already a collaborator for this site"]}
            )

        user.groups.add(Group.objects.get(name=group_name))

        # user.role normally gets set by the query in the view, but we need to manually set/update it here
        user.role = role
        return user

    def update(self, instance, validated_data):
        """ Change a collaborator's permission group for the website """
        website = self.website
        user = instance
        role = validated_data.get("role")
        group_name = permissions_group_name_for_role(role, website)

        # User should only belong to one group per website
        for group in get_groups_with_perms(website):
            if group_name and group.name == group_name:
                user.groups.add(group)
            else:
                user.groups.remove(group)

        # user.role normally gets set by the query in the view, but we need to manually set/update it here
        user.role = role
        return user

    class Meta:
        fields = ["user_id", "email", "name", "group", "role"]


class WebsiteContentSerializer(serializers.ModelSerializer):
    """Serializes WebsiteContent for the list view"""

    class Meta:
        model = WebsiteContent
        read_only_fields = ["text_id", "title", "type", "updated_on"]
        # See WebsiteContentCreateSerializer below for creating new WebsiteContent objects
        fields = read_only_fields


class WebsiteContentDetailSerializer(
    serializers.ModelSerializer, RequestUserSerializerMixin
):
    """Serializes more parts of WebsiteContent, including content or other things which are too big for the list view"""

    content_context = serializers.SerializerMethodField()

    def update(self, instance, validated_data):
        """Add updated_by to the data"""
        if instance.type == "resource":
            update_youtube_thumbnail(
                instance.website.uuid, validated_data.get("metadata"), overwrite=True
            )
        if "file" in validated_data:
            if "metadata" not in validated_data:
                validated_data["metadata"] = {}
            validated_data["metadata"]["file_type"] = detect_mime_type(
                validated_data["file"]
            )
        instance = super().update(
            instance, {"updated_by": self.user_from_request(), **validated_data}
        )
        update_website_backend(instance.website)
        return instance

    def get_content_context(self, instance):
        """
        Create mapping of uuid to a display name for any values in the metadata
        """
        if not self.context or not self.context.get("content_context"):
            return None

        lookup = defaultdict(list)  # website name -> list of text_id
        metadata = instance.metadata or {}
        site_config = SiteConfig(instance.website.starter.config)
        for field in site_config.iter_fields():
            widget = field.field.get("widget")
            if widget in ("relation", "menu"):
                try:
                    if field.parent_field is None:
                        value = metadata.get(field.field["name"])
                    else:
                        value = metadata.get(field.parent_field["name"], {}).get(
                            field.field["name"]
                        )

                    if widget == "relation":
                        content = value["content"]
                        website_name = value["website"]
                        if isinstance(content, str):
                            content = [content]
                        lookup[website_name].extend(content)
                    elif widget == "menu":
                        website_name = instance.website.name
                        lookup[website_name].extend(
                            [
                                item["identifier"]
                                for item in value
                                if not item["identifier"].startswith(
                                    constants.EXTERNAL_IDENTIFIER_PREFIX
                                )
                            ]
                        )

                except (AttributeError, KeyError, TypeError):
                    # Either missing or malformed relation field value
                    continue

        contents = []
        for website_name, text_ids in lookup.items():
            contents.extend(
                WebsiteContent.objects.filter(
                    website__name=website_name, text_id__in=text_ids
                )
            )
        return WebsiteContentDetailSerializer(
            contents, many=True, context={"content_context": False}
        ).data

    def to_representation(self, instance):
        """Add the file field name and url to the serializer if a file exists"""
        result = super().to_representation(instance)
        if instance.file:
            file_field = instance.get_config_file_field()
            if file_field:
                result[file_field["name"]] = instance.file.url
        return result

    class Meta:
        model = WebsiteContent
        read_only_fields = ["text_id", "type", "content_context"]
        fields = read_only_fields + [
            "title",
            "markdown",
            "metadata",
            "file",
            "updated_on",
        ]


class WebsiteContentCreateSerializer(
    serializers.ModelSerializer, RequestUserSerializerMixin
):
    """Serializer which creates a new WebsiteContent"""

    def create(self, validated_data):
        user = self.user_from_request()
        added_context_data = {
            field: self.context[field]
            for field in {"is_page_content", "filename", "dirpath", "text_id"}
            if field in self.context
        }
        if validated_data.get("type") == "resource":
            update_youtube_thumbnail(
                self.context["website_id"], validated_data.get("metadata")
            )

        if "file" in validated_data:
            if "metadata" not in validated_data:
                validated_data["metadata"] = {}
            validated_data["metadata"]["file_type"] = detect_mime_type(
                validated_data["file"]
            )

        instance = super().create(
            {
                "website_id": self.context["website_id"],
                "owner": user,
                "updated_by": user,
                **validated_data,
                **added_context_data,
            }
        )
        update_website_backend(instance.website)
        return instance

    class Meta:
        model = WebsiteContent
        fields = [
            "text_id",
            "type",
            "title",
            "markdown",
            "metadata",
            "filename",
            "dirpath",
            "file",
            "is_page_content",
        ]


class WebsiteCollectionSerializer(
    serializers.ModelSerializer, RequestUserSerializerMixin
):
    """Serializer for WebsiteCollections"""

    def create(self, validated_data):
        """need to override to set owner"""
        validated_data["owner"] = self.user_from_request()
        with transaction.atomic():
            collection = super().create(validated_data)
        return collection

    def update(self, instance, validated_data):
        """gotta pop out owner if it's there"""
        validated_data.pop("owner", None)
        with transaction.atomic():
            collection = super().update(instance, validated_data)
        return collection

    class Meta:
        model = WebsiteCollection
        read_only_fields = ["id"]
        fields = read_only_fields + ["title", "description"]
        extra_kwargs = {"owner": {"write_only": True}}


class WebsiteCollectionItemSerializer(serializers.ModelSerializer):
    """Serializer for WebsiteCollectionItems"""

    website_title = serializers.SerializerMethodField(read_only=True)

    def get_website_title(self, obj):
        """Get the title of the """
        return obj.website.title

    class Meta:
        model = WebsiteCollectionItem
        read_only_fields = ["website_collection", "id"]
        fields = read_only_fields + ["position", "website", "website_title"]
        extra_kwargs = {"position": {"required": False}}

    def create(self, validated_data):
        website_collection = WebsiteCollection.objects.get(
            id=self.website_collection_id
        )
        items = WebsiteCollectionItem.objects.filter(
            website_collection=website_collection
        )
        position = (
            items.aggregate(Max("position"))["position__max"] or items.count()
        ) + 1
        item, _ = WebsiteCollectionItem.objects.get_or_create(
            website_collection=website_collection,
            website=validated_data["website"],
            defaults={"position": position},
        )
        return item

    @property
    def website_collection_id(self):
        """get the collection id"""
        return self.context["website_collection_id"]

    def update(self, instance, validated_data):
        """this position update algorithm is copied over from user lists in
        open-discussions. see here:
        https://github.com/mitodl/open-discussions/blob/master/course_catalog/serializers.py#L504

        if we're moving our item towards the head of the list (i.e. decreasing
        its index) we need to increment by one the position of every item
        between its current position and its new position.

        likewise, if we're moving it down toward the tail of the list (i.e.
        increasing its index) then we need to decrement by one the position of
        every item between it's current position and its new position.
        """
        new_position = validated_data["position"]
        with transaction.atomic():
            if new_position > instance.position:
                # move items between the old and new positions up, inclusive of the new position
                WebsiteCollectionItem.objects.filter(
                    website_collection=self.website_collection_id,
                    position__lte=new_position,
                    position__gt=instance.position,
                ).update(position=F("position") - 1)
            else:
                # move items between the old and new positions down, inclusive of the new position
                WebsiteCollectionItem.objects.filter(
                    website_collection=self.website_collection_id,
                    position__lt=instance.position,
                    position__gte=new_position,
                ).update(position=F("position") + 1)
            # now move the item into place
            instance.position = new_position
            instance.save()

        return instance
