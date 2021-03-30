"""
Test end to end django views.
"""
import json

import pytest
from django.urls import reverse

from users.factories import UserFactory


pytestmark = [
    pytest.mark.django_db,
]


def test_index_view(client):
    """Verify the index view is as expected"""
    response = client.get(reverse("main-index"))
    assert response.status_code == 200


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


@pytest.mark.parametrize("is_authenticated", [True, False])
def test_js_settings(settings, client, is_authenticated):
    """Verify that JS settings render correctly"""
    settings.GA_TRACKING_ID = "fake"
    settings.ENVIRONMENT = "test"
    settings.VERSION = "4.5.6"
    settings.WEBPACK_USE_DEV_SERVER = False

    user = UserFactory.create()

    if is_authenticated:
        client.force_login(user)

    response = client.get(reverse("main-index"))

    js_settings = json.loads(response.context["js_settings_json"])
    assert js_settings == {
        "gaTrackingID": "fake",
        "public_path": "/static/bundles/",
        "environment": settings.ENVIRONMENT,
        "sentry_dsn": "",
        "release_version": settings.VERSION,
        "user": {
            "username": user.username,
            "email": user.email,
            "name": user.name,
        }
        if is_authenticated
        else None,
    }
