"""Custom permissions"""
from rest_framework import permissions


def is_readonly(request):
    """
    Returns True if the request uses a readonly verb

    Args:
        request (HTTPRequest): A request

    Returns:
        bool: True if the request method is readonly
    """
    return request.method in permissions.SAFE_METHODS


class ReadonlyPermission(permissions.BasePermission):
    """Allows read-only requests through for any user"""

    def has_permission(self, request, view):
        """Return true if the request is read-only"""
        return request.method in permissions.SAFE_METHODS
