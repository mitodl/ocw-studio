"""Tests for social auth backends"""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from social_core.exceptions import AuthTokenError
from social_core.tests.models import TestStorage
from social_core.tests.strategy import TestStrategy

from users import backends
from users.backends import KeycloakJWKSOAuth2

REALM_URL = "https://sso.example.com/realms/ocw-studio"
CLIENT_ID = "ocw-studio"


def _signing_key(kid):
    """Generate an RSA key and its public JWK"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return private_key, jwk


def _access_token(private_key, kid, audience=CLIENT_ID):
    """Sign an access token the way Keycloak would"""
    now = int(time.time())
    claims = {
        "aud": audience,
        "exp": now + 300,
        "iat": now,
        "preferred_username": "jdoe",
    }
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def backend():
    """KeycloakJWKSOAuth2 configured against a fake realm"""
    backends._jwks_client.cache_clear()  # noqa: SLF001
    strategy = TestStrategy(TestStorage)
    strategy.set_settings(
        {
            "SOCIAL_AUTH_KEYCLOAK_KEY": CLIENT_ID,
            "SOCIAL_AUTH_KEYCLOAK_ACCESS_TOKEN_URL": (
                f"{REALM_URL}/protocol/openid-connect/token"
            ),
        }
    )
    yield KeycloakJWKSOAuth2(strategy)
    backends._jwks_client.cache_clear()  # noqa: SLF001


@pytest.fixture
def realm_keys(mocker):
    """Serve a mutable list of JWKs from the realm certs endpoint"""
    keys = []
    fetch = mocker.patch.object(
        jwt.PyJWKClient, "fetch_data", side_effect=lambda: {"keys": list(keys)}
    )
    return keys, fetch


def test_jwks_url(backend):
    """The JWKS URL sits next to the token endpoint"""
    assert backend.jwks_url() == f"{REALM_URL}/protocol/openid-connect/certs"


def test_jwks_url_rejects_non_keycloak_token_url(backend):
    """A token URL that isn't a Keycloak realm endpoint fails loudly"""
    backend.strategy.set_settings(
        {"SOCIAL_AUTH_KEYCLOAK_ACCESS_TOKEN_URL": "https://example.com/token"}
    )
    with pytest.raises(ValueError, match="ACCESS_TOKEN_URL"):
        backend.jwks_url()


def test_user_data_survives_key_rotation(backend, realm_keys):
    """Tokens signed by a newly rotated-in key verify without reconfiguration"""
    keys, fetch = realm_keys
    old_private, old_jwk = _signing_key("old")
    keys.append(old_jwk)
    assert (
        backend.user_data(_access_token(old_private, "old"))["preferred_username"]
        == "jdoe"
    )

    new_private, new_jwk = _signing_key("new")
    keys.append(new_jwk)
    assert (
        backend.user_data(_access_token(new_private, "new"))["preferred_username"]
        == "jdoe"
    )
    assert fetch.call_count == 2


@pytest.mark.parametrize(
    ("kid", "signed_by_realm", "audience"),
    [
        ("unknown", False, CLIENT_ID),  # signed by a key the realm doesn't publish
        ("realm", False, CLIENT_ID),  # claims a published kid, signed by another key
        ("realm", True, "other"),  # issued to another client in the realm
    ],
)
def test_user_data_rejects_bad_tokens(
    backend, realm_keys, kid, signed_by_realm, audience
):
    """Invalid tokens raise AuthTokenError rather than a bare PyJWT error"""
    keys, _ = realm_keys
    realm_private, realm_jwk = _signing_key("realm")
    keys.append(realm_jwk)
    private_key = realm_private if signed_by_realm else _signing_key("x")[0]
    with pytest.raises(AuthTokenError):
        backend.user_data(_access_token(private_key, kid, audience=audience))


def test_user_data_rejects_malformed_token(backend, realm_keys):
    """A malformed token raises AuthTokenError"""
    with pytest.raises(AuthTokenError):
        backend.user_data("not-a-jwt")
