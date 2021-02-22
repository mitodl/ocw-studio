""" Serializers for websites """
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from main.serializers import WriteableSerializerMethodField
from users.models import User
from websites import constants
from websites.models import Website, WebsiteStarter
from websites.permissions import is_global_admin


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

    def create(self, validated_data):
        """Ensure that the website is created by the requesting user"""
        request = self.context.get("request")
        if request and hasattr(request, "user") and isinstance(request.user, User):
            validated_data["owner"] = request.user
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
        fields = WebsiteSerializer.Meta.fields


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
