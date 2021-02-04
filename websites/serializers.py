""" Serializers for websites """
import yaml
from rest_framework import serializers

from websites.models import Website, WebsiteStarter


class WebsiteStarterSerializer(serializers.ModelSerializer):
    """ Serializer for website starters """

    class Meta:
        model = WebsiteStarter
        fields = ["id", "name", "path", "source", "commit", "slug"]


class WebsiteStarterDetailSerializer(serializers.ModelSerializer):
    """ Serializer for website starters with serialized config """

    config = serializers.SerializerMethodField()

    def get_config(self, instance):
        """Returns parsed YAML config"""
        return yaml.load(instance.config, Loader=yaml.Loader)

    class Meta:
        model = WebsiteStarter
        fields = WebsiteStarterSerializer.Meta.fields + ["config"]


class WebsiteSerializer(serializers.ModelSerializer):
    """ Serializer for websites """

    starter = WebsiteStarterSerializer(read_only=True)

    class Meta:
        model = Website
        fields = "__all__"
