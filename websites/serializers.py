""" Serializers for websites """
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import F, Max
from guardian.shortcuts import get_groups_with_perms, get_users_with_perms
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from content_sync.api import create_website_backend, update_website_backend
from main.serializers import RequestUserSerializerMixin
from users.models import User
from websites import constants
from websites.models import (
    Website,
    WebsiteCollection,
    WebsiteCollectionItem,
    WebsiteContent,
    WebsiteStarter,
)
from websites.permissions import is_global_admin, is_site_admin
from websites.utils import permissions_group_name_for_role


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
            "title",
            "source",
            "publish_date",
            "metadata",
            "starter",
            "owner",
        ]
        extra_kwargs = {"owner": {"write_only": True}}


class WebsiteDetailSerializer(serializers.ModelSerializer, RequestUserSerializerMixin):
    """ Serializer for websites with serialized config """

    starter = WebsiteStarterDetailSerializer(read_only=True)
    is_admin = serializers.SerializerMethodField(read_only=True)

    def get_is_admin(self, obj):
        """ Determine if the request user is an admin"""
        user = self.user_from_request()
        if user:
            return is_site_admin(user, obj)
        return False

    def create(self, validated_data):
        """Ensure that the website is created by the requesting user"""
        validated_data["owner"] = self.user_from_request()
        with transaction.atomic():
            website = super().create(validated_data)
        create_website_backend(website)
        return website

    def update(self, instance, validated_data):
        """ Remove owner attribute if present, it should not be changed"""
        validated_data.pop("owner", None)
        with transaction.atomic():
            website = super().update(instance, validated_data)
        update_website_backend(website)
        return website

    class Meta:
        model = Website
        fields = WebsiteSerializer.Meta.fields + ["is_admin"]


class WebsiteWriteSerializer(WebsiteDetailSerializer):
    """
    Deserializer for websites
    NOTE: This is needed because DRF does not directly support saving a related field using just an id. We want to
    deserialize and save Website objects and save the related WebsiteStarter as an id, but there is no clean way to
    do that with DRF, hence this added serializer class.
    """

    starter = serializers.PrimaryKeyRelatedField(
        queryset=WebsiteStarter.objects.all(), write_only=True
    )


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
        read_only_fields = ["text_id", "title", "type"]
        # See WebsiteContentCreateSerializer below for creating new WebsiteContent objects
        fields = read_only_fields


class WebsiteContentDetailSerializer(
    serializers.ModelSerializer, RequestUserSerializerMixin
):
    """Serializes more parts of WebsiteContent, including content or other things which are too big for the list view"""

    def update(self, instance, validated_data):
        """Add updated_by to the data"""
        instance = super().update(
            instance, {"updated_by": self.user_from_request(), **validated_data}
        )
        update_website_backend(instance.website)
        return instance

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
        read_only_fields = ["text_id", "type"]
        fields = read_only_fields + [
            "title",
            "markdown",
            "metadata",
            "file",
        ]


class WebsiteContentCreateSerializer(
    serializers.ModelSerializer, RequestUserSerializerMixin
):
    """Serializer which creates a new WebsiteContent"""

    def create(self, validated_data):
        user = self.user_from_request()
        added_context_data = {
            field: self.context[field]
            for field in {"is_page_content", "filename", "dirpath"}
            if field in self.context
        }
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

    class Meta:
        model = WebsiteCollectionItem
        read_only_fields = ["website_collection", "id"]
        fields = read_only_fields + ["position", "website"]
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
