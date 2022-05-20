""" Serializers for websites """
import logging
import re
from collections import defaultdict
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import transaction
from guardian.shortcuts import get_groups_with_perms, get_users_with_perms
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from content_sync.api import create_website_backend, update_website_backend
from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.models import ContentSyncState
from gdrive_sync.api import gdrive_root_url, is_gdrive_enabled
from gdrive_sync.tasks import create_gdrive_folders
from main.serializers import RequestUserSerializerMixin
from users.models import User
from websites import constants
from websites.api import (
    detect_mime_type,
    incomplete_content_warnings,
    sync_website_title,
    update_youtube_thumbnail,
)
from websites.constants import CONTENT_TYPE_METADATA, CONTENT_TYPE_RESOURCE
from websites.models import Website, WebsiteContent, WebsiteStarter
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


class WebsiteValidationMixin(serializers.Serializer):
    """Serializer for website publishing content validation"""

    content_warnings = serializers.SerializerMethodField(read_only=True)

    def get_content_warnings(self, instance):
        """Return any missing content data warnings"""
        return incomplete_content_warnings(instance)


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
            "first_published_to_production",
            "metadata",
            "starter",
            "owner",
            "url_path",
        ]
        extra_kwargs = {"owner": {"write_only": True}}


class WebsiteUrlSerializer(serializers.ModelSerializer):
    """ Serializer for assigning website urls """

    def validate_url_path(self, value):
        """
        Check that the website url will be unique and template sections have been replaced.
        """
        if not value and self.instance.url_path is None:
            raise serializers.ValidationError("The URL path cannot be blank")
        url = self.instance.assemble_full_url_path(value)
        if self.instance.publish_date and url != self.instance.url_path:
            raise serializers.ValidationError(
                "The URL cannot be changed after publishing."
            )
        if re.findall(r"[\[\]]+", url):
            raise serializers.ValidationError(
                "You must replace the url sections in brackets"
            )
        if (
            url
            and Website.objects.filter(url_path=url)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError("The website URL is not unique")
        return value

    def update(self, instance, validated_data):
        """ Update the website url_path"""
        url_path = validated_data.get("url_path")
        with transaction.atomic():
            instance.url_path = instance.assemble_full_url_path(url_path)
            instance.save()
            # Force a backend resync of all associated content with file paths
            ContentSyncState.objects.filter(
                content__in=instance.websitecontent_set.filter(file__isnull=False)
            ).update(synced_checksum=None)

    class Meta:
        model = Website
        fields = [
            "url_path",
        ]


class WebsiteMassBuildSerializer(serializers.ModelSerializer):
    """ Serializer for mass building websites """

    starter_slug = serializers.SerializerMethodField(read_only=True)
    base_url = serializers.SerializerMethodField(read_only=True)
    site_url = serializers.SerializerMethodField(read_only=True)
    s3_path = serializers.SerializerMethodField(read_only=True)

    def get_starter_slug(self, instance):
        """Get the website starter slug"""
        return instance.starter.slug

    def get_site_url(self, instance):
        """Get the website relative url"""
        return instance.url_path

    def get_s3_path(self, instance):
        """Get the website s3 path"""
        return instance.s3_path

    def get_base_url(self, instance):
        """Get the base url (should be same as site_url except for the root site)"""
        if instance.name == settings.ROOT_WEBSITE_NAME:
            return ""
        return self.get_site_url(instance)

    class Meta:
        model = Website
        fields = ["name", "short_id", "starter_slug", "site_url", "base_url", "s3_path"]
        read_only_fields = fields


class WebsiteUnpublishSerializer(serializers.ModelSerializer):
    """ Serializer for removing unpublished websites """

    site_url = serializers.SerializerMethodField(read_only=True)
    site_uid = serializers.SerializerMethodField(read_only=True)

    def get_site_url(self, instance):
        """Get the website relative url"""
        return instance.url_path

    def get_site_uid(self, instance):
        """Get the website uid"""
        meta_content = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_METADATA, website=instance
        ).first()
        legacy_uid = (
            meta_content.metadata.get("legacy_uid", "")
            if meta_content is not None
            else ""
        ).replace("-", "")
        return legacy_uid or instance.uuid.hex

    class Meta:
        model = Website
        fields = [
            "name",
            "site_url",
            "site_uid",
        ]
        read_only_fields = fields


class WebsiteUrlSuggestionMixin(serializers.Serializer):
    """Add the url_suggestion custom field"""

    url_suggestion = serializers.SerializerMethodField(read_only=True)

    def get_url_suggestion(self, instance):
        """Get the current or potential url path for the site"""
        return instance.get_url_path(with_prefix=False)


class WebsiteDetailSerializer(
    serializers.ModelSerializer,
    WebsiteGoogleDriveMixin,
    WebsiteValidationMixin,
    RequestUserSerializerMixin,
    WebsiteUrlSuggestionMixin,
):
    """ Serializer for websites with serialized config """

    starter = WebsiteStarterDetailSerializer(read_only=True)
    is_admin = serializers.SerializerMethodField(read_only=True)
    live_url = serializers.SerializerMethodField(read_only=True)
    draft_url = serializers.SerializerMethodField(read_only=True)

    def get_is_admin(self, obj):
        """ Determine if the request user is an admin"""
        user = self.user_from_request()
        if user:
            return is_site_admin(user, obj)
        return False

    def get_live_url(self, instance):
        """Get the live url for the site"""
        return instance.get_full_url(version=VERSION_LIVE)

    def get_draft_url(self, instance):
        """Get the draft url for the site"""
        return instance.get_full_url(version=VERSION_DRAFT)

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
            "url_path",
            "url_suggestion",
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
            "content_warnings",
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
            "content_warnings",
            "url_path",
        ]


class WebsiteStatusSerializer(
    serializers.ModelSerializer,
    WebsiteGoogleDriveMixin,
    WebsiteValidationMixin,
    WebsiteUrlSuggestionMixin,
):
    """Serializer for website status fields"""

    class Meta:
        model = Website
        fields = [
            "uuid",
            "name",
            "title",
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
            "content_warnings",
            "url_suggestion",
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
    url_path = serializers.SerializerMethodField()

    def update(self, instance, validated_data):
        """Add updated_by to the data"""
        if instance.type == CONTENT_TYPE_RESOURCE:
            update_youtube_thumbnail(
                instance.website.uuid, validated_data.get("metadata"), overwrite=True
            )
        if "file" in validated_data:
            if "metadata" not in validated_data:
                validated_data["metadata"] = {}
            validated_data["metadata"]["file_type"] = detect_mime_type(
                validated_data["file"]
            )
        existing_metadata = instance.metadata if instance.metadata else {}
        if "metadata" in validated_data:
            validated_data["metadata"] = {
                **existing_metadata,
                **validated_data["metadata"],
            }
        instance = super().update(
            instance, {"updated_by": self.user_from_request(), **validated_data}
        )
        update_website_backend(instance.website)
        # Sync the metadata title and website title if appropriate
        if instance.type == CONTENT_TYPE_METADATA:
            sync_website_title(instance)
        return instance

    def get_url_path(self, instance):
        """Get the parent website url path"""
        return instance.website.url_path

    def get_content_context(self, instance):  # pylint:disable=too-many-branches
        """
        Create mapping of uuid to a display name for any values in the metadata
        """
        if not self.context or not self.context.get("content_context"):
            return None

        lookup = defaultdict(list)  # website name -> list of text_id
        metadata = instance.metadata or {}
        site_config = SiteConfig(instance.website.starter.config)
        for field in site_config.iter_fields():  # pylint:disable=too-many-nested-blocks
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

                        if (
                            isinstance(content, list)
                            and len(content) > 0
                            and isinstance(content[0], list)
                        ):
                            # this is the data from a 'global' relation widget,
                            # which is a list of [content_uuid, website_name]
                            # tuples
                            for [content_uuid, website_name] in content:
                                lookup[website_name].extend([content_uuid])
                        else:
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
        read_only_fields = ["text_id", "type", "content_context", "url_path"]
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
        if validated_data.get("type") == CONTENT_TYPE_RESOURCE:
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
        if instance.type == CONTENT_TYPE_METADATA:
            sync_website_title(instance)
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
