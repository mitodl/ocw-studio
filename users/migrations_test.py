"""Tests for users data migrations"""

import base64
import importlib
import json
import time

import pytest
from django.apps import apps as django_apps
from django.test import RequestFactory
from social_core.exceptions import AuthAssociationError
from social_core.pipeline.social_auth import social_user
from social_django.models import UserSocialAuth
from social_django.utils import load_backend, load_strategy

from users.factories import UserFactory

migration = importlib.import_module("users.migrations.0003_backfill_keycloak_sub")

pytestmark = pytest.mark.django_db


def _jwt(claims):
    """Encode claims as the payload of an unsigned, structurally valid JWT"""

    def segment(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{segment({'alg': 'RS256'})}.{segment(claims)}.c2lnbmF0dXJl"


def _claims(sub, **extra):
    """Build Keycloak-shaped token claims, optionally without a subject"""
    claims = {
        "exp": int(time.time()) + 300,
        "preferred_username": "jdoe@mit.edu",
        "email": "jdoe@mit.edu",
        **extra,
    }
    if sub is not None:
        claims["sub"] = sub
    return claims


def _association(user, uid, extra_data, provider="keycloak", id_key="username"):
    """Create a UserSocialAuth row the way a pre-6.0 login would have"""
    return UserSocialAuth.objects.create(
        user=user, provider=provider, uid=uid, id_key=id_key, extra_data=extra_data
    )


def _run():
    """Run the data migration against the live app registry"""
    migration.backfill_keycloak_sub(django_apps, None)


def test_backfill_prefers_the_access_token_subject():
    """The access token's subject wins, since that is what the backend reads"""
    social = _association(
        UserFactory.create(),
        "jdoe@mit.edu",
        {
            "access_token": _jwt(_claims("access-sub")),
            "id_token": _jwt(_claims("id-sub")),
        },
    )
    _run()
    social.refresh_from_db()
    assert social.extra_data["sub"] == "access-sub"


def test_backfill_falls_back_to_the_id_token():
    """A realm that omits `sub` from the access token still backfills"""
    social = _association(
        UserFactory.create(),
        "jdoe@mit.edu",
        {
            "access_token": _jwt(_claims(None)),
            "id_token": _jwt(_claims("id-sub")),
        },
    )
    _run()
    social.refresh_from_db()
    assert social.extra_data["sub"] == "id-sub"


def test_backfill_leaves_the_uid_and_id_key_alone():
    """Migration only adds evidence; social-core performs the migration itself"""
    social = _association(
        UserFactory.create(),
        "jdoe@mit.edu",
        {"access_token": _jwt(_claims("access-sub"))},
    )
    _run()
    social.refresh_from_db()
    assert social.uid == "jdoe@mit.edu"
    assert social.id_key == "username"


def test_backfill_keeps_an_existing_subject():
    """An association that already carries evidence is left untouched"""
    social = _association(
        UserFactory.create(),
        "already-migrated",
        {"sub": "original-sub", "access_token": _jwt(_claims("access-sub"))},
        id_key="sub",
    )
    _run()
    social.refresh_from_db()
    assert social.extra_data["sub"] == "original-sub"


@pytest.mark.parametrize(
    "extra_data",
    [
        pytest.param({}, id="no-tokens"),
        pytest.param({"access_token": "not-a-jwt"}, id="malformed-token"),
        pytest.param({"access_token": _jwt(_claims(None))}, id="no-sub-claim"),
        pytest.param({"access_token": "a.!!!not-base64!!!.c"}, id="undecodable"),
        pytest.param({"access_token": None}, id="null-token"),
        pytest.param({"access_token": _jwt(["not", "an", "object"])}, id="non-object"),
    ],
)
def test_backfill_skips_rows_without_a_usable_subject(extra_data):
    """A row the subject cannot be read from is left for manual handling"""
    social = _association(UserFactory.create(), "jdoe@mit.edu", extra_data)
    _run()
    social.refresh_from_db()
    assert "sub" not in social.extra_data


def test_backfill_ignores_other_providers():
    """Only Keycloak associations are touched"""
    social = _association(
        UserFactory.create(),
        "jdoe@mit.edu",
        {"access_token": _jwt(_claims("access-sub"))},
        provider="github",
    )
    _run()
    social.refresh_from_db()
    assert "sub" not in social.extra_data


def test_backfill_handles_many_associations():
    """Every eligible row is updated, past one bulk_update batch"""
    expected = {}
    for index in range(150):
        user = UserFactory.create()
        sub = f"sub-{index}"
        social = _association(
            user, f"user{index}@mit.edu", {"access_token": _jwt(_claims(sub))}
        )
        expected[social.pk] = sub
    _run()
    actual = {
        social.pk: social.extra_data.get("sub")
        for social in UserSocialAuth.objects.filter(pk__in=expected)
    }
    assert actual == expected


def test_backfill_unblocks_the_social_core_6_identifier_migration(settings):
    """
    End to end: the backfill is what lets an existing association survive.

    social-core 6 re-keys Keycloak accounts from the mutable `username` to the
    immutable `sub`, and refuses to do so without a stored `sub` to check the
    incoming one against. This is the regression test for that whole path:
    before the backfill the login is rejected, after it the row migrates.
    """
    settings.SOCIAL_AUTH_KEYCLOAK_KEY = "ocw-studio"

    sub = "e3b0c442-98fc-1c14-9afb-f4c8996fb924"
    user = UserFactory.create()
    social = _association(user, "jdoe@mit.edu", {"access_token": _jwt(_claims(sub))})

    request = RequestFactory().get("/")
    request.session = {}
    backend = load_backend(load_strategy(request), "keycloak", redirect_uri=None)

    def attempt():
        return social_user(
            backend,
            sub,
            None,
            id_key="sub",
            response={"sub": sub, "preferred_username": "jdoe@mit.edu"},
            legacy_identifiers=[("username", "jdoe@mit.edu")],
        )

    with pytest.raises(AuthAssociationError):
        attempt()

    _run()

    result = attempt()
    assert result["social"].pk == social.pk
    assert result["user"] == user

    social.refresh_from_db()
    assert social.uid == sub
    assert social.id_key == "sub"
