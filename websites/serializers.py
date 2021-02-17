""" Serializers for websites """
from django.db import transaction
from rest_framework import serializers

from users.models import User
from websites.models import Website, WebsiteStarter


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
