""" Serializers for websites """
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from main.serializers import WriteableSerializerMethodField
from users.models import User
from websites import constants
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.permissions import is_global_admin, is_site_admin


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


class WebsiteDetailSerializer(serializers.ModelSerializer):
    """ Serializer for websites with serialized config """

    starter = WebsiteStarterDetailSerializer(read_only=True)
    is_admin = serializers.SerializerMethodField(read_only=True)

    def user_from_request(self):
        """ Get the user from the request context """
        request = self.context.get("request")
        if request and hasattr(request, "user") and isinstance(request.user, User):
            return request.user
        return None

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
        return website

    def update(self, instance, validated_data):
        """ Remove owner attribute if present, it should not be changed"""
        validated_data.pop("owner", None)
        with transaction.atomic():
            website = super().update(instance, validated_data)
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

    role = WriteableSerializerMethodField()
    email = serializers.EmailField(allow_null=True, required=False)
    group = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)

    def get_role(self, obj):
        """ Get the role based on the group """
        group = obj.group if isinstance(obj, User) else obj.get("group", None)
        if group:
            group_role_map = {v: k for k, v in constants.ROLE_GROUP_MAPPING.items()}
            group_prefix = f"{group.rsplit('_', 1)[0]}_"
            if group_prefix in group_role_map.keys():
                return group_role_map[group_prefix]
            return group
        return obj.get("role", None)

    def validate_role(self, role):
        """ The role should be admin or editor"""
        if not role or role not in constants.ROLE_GROUP_MAPPING.keys():
            raise ValidationError("Invalid role")
        return {"role": role}

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
            raise ValidationError("Role is required")
        if not self.instance and not attrs.get("email"):
            raise ValidationError("Email is required")
        return attrs

    class Meta:
        fields = ["username", "email", "name", "group", "role"]


class WebsiteContentSerializer(serializers.ModelSerializer):
    """Serializes parts of WebsiteContent"""

    class Meta:
        model = WebsiteContent
        fields = ["uuid", "title", "type"]
        read_only_fields = ["uuid", "type"]


class WebsiteContentDetailSerializer(serializers.ModelSerializer):
    """Serializes more parts of WebsiteContent, including content or other things which are too big for the list view"""

    class Meta:
        model = WebsiteContent
        fields = WebsiteContentSerializer.Meta.fields + ["markdown"]
        read_only_fields = WebsiteContentSerializer.Meta.read_only_fields


class WebsiteContentCreateSerializer(serializers.ModelSerializer):
    """Serializer which creates a new WebsiteContent"""

    def create(self, validated_data):
        """Add the website_id to the data"""
        website_name = self.context["view"].kwargs["parent_lookup_website"]
        website = Website.objects.get(name=website_name)
        return super().create({"website_id": website.pk, **validated_data})

    class Meta:
        model = WebsiteContent
        fields = ["type", "title", "markdown", "uuid"]
        # we want uuid in the returned result but we also want to ignore any attempt to set it on create
        read_only_fields = ["uuid"]
