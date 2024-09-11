"""
ocw_studio views
"""

import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from mitol.common.utils.webpack import webpack_public_path
from rest_framework.pagination import LimitOffsetPagination

from gdrive_sync.api import is_gdrive_enabled
from websites import constants


def _index(request):
    """Render the view for React pages"""

    js_settings = {
        "gaTrackingID": settings.GA_TRACKING_ID,
        "environment": settings.ENVIRONMENT,
        "public_path": webpack_public_path(request),
        "release_version": settings.VERSION,
        "sentry_dsn": settings.SENTRY_DSN,
        "gdrive_enabled": is_gdrive_enabled(),
        "features": settings.FEATURES,
        "features_default": settings.FEATURES_DEFAULT,
        "posthog_api_host": settings.POSTHOG_API_HOST,
        "posthog_project_api_key": settings.POSTHOG_PROJECT_API_KEY,
    }

    user = request.user

    js_settings["user"] = (
        {
            "username": user.username,
            "email": user.email,
            "name": user.name,
            "canAddWebsite": user.has_perm(constants.PERMISSION_ADD),
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


def public_index(
    request,
    *args,  # noqa: ARG001
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Render a React page. The frontend will render an appropriate UI based on the URL
    """
    return _index(request)


@login_required
def restricted_index(
    request,
    *args,  # noqa: ARG001
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Render a React page. The frontend will render an appropriate UI based on the URL
    """
    return _index(request)


class DefaultPagination(LimitOffsetPagination):
    """
    Default pagination class for viewsets
    """

    default_limit = 10
    max_limit = 100
