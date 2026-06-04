"""
ocw_studio views
"""

import json
from urllib.parse import urlencode, urlparse, urlunparse

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from mitol.common.utils.webpack import webpack_public_path
from rest_framework.pagination import LimitOffsetPagination

from gdrive_sync.api import is_gdrive_enabled
from websites import constants

KEYCLOAK_AUTH_SUFFIX = "/protocol/openid-connect/auth"
KEYCLOAK_LOGOUT_SUFFIX = "/protocol/openid-connect/logout"


@ensure_csrf_cookie
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
        "sitemapDomain": settings.SITEMAP_DOMAIN,
        "maxTitle": constants.CONTENT_FILENAME_MAX_LEN,
        "deletableContentTypes": settings.OCW_STUDIO_DELETABLE_CONTENT_TYPES,
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


def _get_keycloak_id_token_hint(user):
    """Get the Keycloak id_token value from social-auth data if available."""
    if not user.is_authenticated:
        return None

    social_auth = user.social_auth.filter(provider="keycloak").first()
    if not social_auth:
        return None

    extra_data = social_auth.extra_data
    if not isinstance(extra_data, dict):
        return None

    return extra_data.get("id_token")


def _build_keycloak_logout_url(request, id_token_hint=None):
    """Build the Keycloak end-session URL from the configured auth URL."""
    auth_url = getattr(settings, "SOCIAL_AUTH_KEYCLOAK_AUTHORIZATION_URL", "")
    client_id = getattr(settings, "SOCIAL_AUTH_KEYCLOAK_KEY", "")
    if not auth_url or not client_id:
        return None

    parsed_auth_url = urlparse(auth_url)
    if not parsed_auth_url.scheme or not parsed_auth_url.netloc:
        return None

    auth_path = parsed_auth_url.path.rstrip("/")
    if not auth_path.endswith(KEYCLOAK_AUTH_SUFFIX):
        return None

    logout_path = f"{auth_path[: -len(KEYCLOAK_AUTH_SUFFIX)]}{KEYCLOAK_LOGOUT_SUFFIX}"
    query_params = {
        "client_id": client_id,
        "post_logout_redirect_uri": request.build_absolute_uri(
            settings.LOGOUT_REDIRECT_URL
        ),
    }
    if id_token_hint:
        query_params["id_token_hint"] = id_token_hint

    return urlunparse(
        parsed_auth_url._replace(
            path=logout_path,
            params="",
            query=urlencode(query_params),
            fragment="",
        )
    )


@require_POST
def global_logout(request):
    """Logout locally and redirect through Keycloak for SSO session termination."""
    id_token_hint = _get_keycloak_id_token_hint(request.user)
    keycloak_logout_url = _build_keycloak_logout_url(request, id_token_hint)

    logout(request)
    return redirect(keycloak_logout_url or settings.LOGOUT_REDIRECT_URL)


class DefaultPagination(LimitOffsetPagination):
    """
    Default pagination class for viewsets
    """

    default_limit = 10
    max_limit = 100
