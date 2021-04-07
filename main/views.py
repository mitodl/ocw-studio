"""
ocw_studio views
"""
import json

from django.conf import settings
from django.shortcuts import render
from mitol.common.utils.webpack import webpack_public_path
from rest_framework.pagination import LimitOffsetPagination


def index(request, *args, **kwargs):  # pylint: disable=unused-argument
    """
    The index view. Display available programs
    """

    js_settings = {
        "gaTrackingID": settings.GA_TRACKING_ID,
        "environment": settings.ENVIRONMENT,
        "public_path": webpack_public_path(request),
        "release_version": settings.VERSION,
        "sentry_dsn": settings.SENTRY_DSN,
    }

    user = request.user

    js_settings["user"] = (
        {
            "username": user.username,
            "email": user.email,
            "name": user.name,
        }
        if user.is_authenticated
        else None
    )

    return render(
        request,
        "index.html",
        context={
            "js_settings_json": json.dumps(js_settings),
        },
    )


class DefaultPagination(LimitOffsetPagination):
    """
    Default pagination class for viewsets
    """

    default_limit = 10
    max_limit = 100
