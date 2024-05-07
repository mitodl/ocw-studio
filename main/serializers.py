"""Common DRF serializers"""

from rest_framework import serializers

from users.models import User


class WriteableSerializerMethodField(serializers.SerializerMethodField):
    """
    A SerializerMethodField which has been marked as not read_only so that submitted data passed validation.
    """  # noqa: E501

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.read_only = False

    def to_internal_value(self, data):
        return data


class RequestUserSerializerMixin:
    """
    A mixin for serializers that need to determine which user made a request
    """

    def user_from_request(self):
        """Get the user from the request context"""
        request = self.context.get("request")
        if request and hasattr(request, "user") and isinstance(request.user, User):
            return request.user
        return None
