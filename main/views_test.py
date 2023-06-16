"""
Test end to end django views.
"""
import json

import pytest
from django.urls import reverse
from rest_framework.status import HTTP_200_OK, HTTP_302_FOUND

from users.factories import UserFactory


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
    "name, is_authenticated, expected_success",
    [
        ["main-index", True, True],
        ["main-index", False, True],
        ["login", True, True],
        ["login", False, True],
        ["sites", True, True],
        ["sites", False, False],
        ["new-site", True, True],
        ["new-site", False, False],
        ["markdown-editor-test", True, True],
        ["markdown-editor-test", False, False],
    ],
)  # pylint: disable=too-many-arguments
@pytest.mark.parametrize("is_gdrive_enabled", [True, False])
def test_react_page( # pylint: disable=too-many-arguments
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
            "user": {
                "username": user.username,
                "email": user.email,
                "name": user.name,
                "canAddWebsite": False,
            }
            if is_authenticated
            else None,
        }
    else:
        assert response.status_code == HTTP_302_FOUND
        assert response.url.startswith("/?next=")
