"""
ocw_studio views
"""
import json

from django.conf import settings
from django.shortcuts import render
from mitol.common.utils.webpack import webpack_public_path


def index(request):
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

    return render(
        request,
        "index.html",
        context={
            "js_settings_json": json.dumps(js_settings),
        },
    )
