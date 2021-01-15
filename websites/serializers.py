""" Serializers for websites """
from rest_framework import serializers

from websites.models import Website


class WebsiteSerializer(serializers.ModelSerializer):
    """ Serializer for websites """

    class Meta:
        model = Website
        fields = "__all__"
