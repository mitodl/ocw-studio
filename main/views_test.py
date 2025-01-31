"""
Test end to end django views.
"""

import json

import pytest
from django.urls import reverse
from rest_framework.status import HTTP_200_OK, HTTP_302_FOUND

from users.factories import UserFactory
from websites.constants import CONTENT_FILENAME_MAX_LEN

pytestmark = [
    pytest.mark.django_db,
]


def test_webpack_url(mocker, settings, client):
    """Verify that webpack bundle src shows up in production"""
    settings.WEBPACK_USE_DEV_SERVER = False
    get_bundle = mocker.patch("mitol.common.templatetags.render_bundle._get_bundle")

    response = client.get(reverse("main-index"))

    bundles = [bundle[0][1] for bundle in get_bundle.call_args_list]
    assert set(bundles) == {
        "root",
        "style",
    }

    js_settings = json.loads(response.context["js_settings_json"])
    assert js_settings["public_path"] == "/static/bundles/"


@pytest.mark.parametrize(
    ("name", "is_authenticated", "expected_success"),
    [
        ["main-index", True, True],  # noqa: PT007
        ["main-index", False, True],  # noqa: PT007
        ["login", True, True],  # noqa: PT007
        ["login", False, True],  # noqa: PT007
        ["sites", True, True],  # noqa: PT007
        ["sites", False, False],  # noqa: PT007
        ["new-site", True, True],  # noqa: PT007
        ["new-site", False, False],  # noqa: PT007
        ["markdown-editor-test", True, True],  # noqa: PT007
        ["markdown-editor-test", False, False],  # noqa: PT007
    ],
)  # pylint: disable=too-many-arguments
@pytest.mark.parametrize("is_gdrive_enabled", [True, False])
def test_react_page(  # pylint: disable=too-many-arguments  # noqa: PLR0913
    settings,
    mocker,
    client,
    name,
    is_authenticated,
    expected_success,
    is_gdrive_enabled,
):
    """Verify that JS settings render correctly for pages used to render React pages"""
    settings.GA_TRACKING_ID = "fake"
    settings.ENVIRONMENT = "test"
    settings.VERSION = "4.5.6"
    settings.WEBPACK_USE_DEV_SERVER = False

    mocker.patch("main.views.is_gdrive_enabled", return_value=is_gdrive_enabled)

    user = UserFactory.create()

    if is_authenticated:
        client.force_login(user)

    response = client.get(reverse(name))
    if expected_success:
        assert response.status_code == HTTP_200_OK
        js_settings = json.loads(response.context["js_settings_json"])
        assert js_settings == {
            "gaTrackingID": "fake",
            "public_path": "/static/bundles/",
            "environment": settings.ENVIRONMENT,
            "sentry_dsn": "",
            "release_version": settings.VERSION,
            "gdrive_enabled": is_gdrive_enabled,
            "user": (
                {
                    "username": user.username,
                    "email": user.email,
                    "name": user.name,
                    "canAddWebsite": False,
                }
                if is_authenticated
                else None
            ),
            "features": settings.FEATURES,
            "features_default": settings.FEATURES_DEFAULT,
            "posthog_api_host": settings.POSTHOG_API_HOST,
            "posthog_project_api_key": settings.POSTHOG_PROJECT_API_KEY,
            "sitemapDomain": settings.SITEMAP_DOMAIN,
            "maxTitle": CONTENT_FILENAME_MAX_LEN,
            "deletableContentTypes": settings.OCW_STUDIO_DELETABLE_CONTENT_TYPES,
        }
    else:
        assert response.status_code == HTTP_302_FOUND
        assert response.url.startswith("/?next=")
