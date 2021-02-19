""" Serializers for websites """
from django.contrib.auth.models import Group
from django.db import transaction
from guardian.shortcuts import get_groups_with_perms, get_users_with_perms
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

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

    group = serializers.CharField(default=None)
    email = serializers.EmailField(allow_null=True)
    name = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)

    def validate_group(self, group):
        """ The group should exist and not be a global group and be for the correct website"""
        if group in (constants.GLOBAL_ADMIN, constants.GLOBAL_AUTHOR):
            raise ValidationError("Cannot assign users to this group")
        if not Group.objects.filter(name=group).exists():
            raise ValidationError("Group does not exist")
        view = self.context.get("view", None)
        if view and hasattr(view, "kwargs"):
            if (
                Website.objects.get(
                    name=view.kwargs.get("parent_lookup_website")
                ).uuid.hex
                not in group
            ):
                raise ValidationError("Not a valid group for this website")
        return group

    def validate_email(self, email):
        """ The user should exist and not be a global admin """
        user = User.objects.filter(email=email).first()
        if not user:
            raise ValidationError("User does not exist")
        if is_global_admin(user):
            raise ValidationError("User is a global admin")
        return email

    def create(self, validated_data):
        """ Add a new website collaborator """
        group = Group.objects.get(name=validated_data["group"])
        website = Website.objects.get(uuid=group.name.split("_")[-1])
        user = User.objects.get(email=validated_data["email"])
        if user in get_users_with_perms(website) or user == website.owner:
            raise ValidationError("User already has permission for this site")
        user.groups.add(group)
        # include group in response JSON
        user.group = group.name
        return user

    def update(self, instance, validated_data):
        """ Update an existing website collaborator """
        group_name = validated_data.get("group")
        website = Website.objects.get(uuid=group_name.split("_")[-1])
        # User should only belong to one group per website
        for group in get_groups_with_perms(website):
            if group_name and group.name == group_name:
                instance.groups.add(group)
            else:
                instance.groups.remove(group)
        # include group in response JSON
        instance.group = group_name
        return instance

    class Meta:
        fields = ["username", "email", "name", "group"]
