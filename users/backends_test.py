"""Tests for social auth backends"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from social_core.exceptions import AuthTokenError
from social_core.tests.models import TestStorage
from social_core.tests.strategy import TestStrategy

from users import backends
from users.backends import KeycloakJWKSOAuth2

REALM_PATH = "/realms/ocw-studio"
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
def realm():
    """
    Serve a mutable list of JWKs from a local realm certs endpoint.

    This is a real HTTP server rather than a patch on PyJWKClient, so the
    client's key set cache and its refresh on an unknown kid both run.
    """
    keys = []
    requests = []

    class CertsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = json.dumps({"keys": list(keys)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), CertsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}{REALM_PATH}"
    yield url, keys, requests
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def backend(realm):
    """KeycloakJWKSOAuth2 configured against the local realm"""
    url, _, _ = realm
    backends._jwks_client.cache_clear()  # noqa: SLF001
    strategy = TestStrategy(TestStorage)
    strategy.set_settings(
        {
            "SOCIAL_AUTH_KEYCLOAK_KEY": CLIENT_ID,
            "SOCIAL_AUTH_KEYCLOAK_ACCESS_TOKEN_URL": (
                f"{url}/protocol/openid-connect/token"
            ),
        }
    )
    yield KeycloakJWKSOAuth2(strategy)
    backends._jwks_client.cache_clear()  # noqa: SLF001


def test_jwks_url(backend, realm):
    """The JWKS URL sits next to the token endpoint"""
    url, _, _ = realm
    assert backend.jwks_url() == f"{url}/protocol/openid-connect/certs"


def test_jwks_url_rejects_non_keycloak_token_url(backend):
    """A token URL that isn't a Keycloak realm endpoint fails loudly"""
    backend.strategy.set_settings(
        {"SOCIAL_AUTH_KEYCLOAK_ACCESS_TOKEN_URL": "https://example.com/token"}
    )
    with pytest.raises(ValueError, match="ACCESS_TOKEN_URL"):
        backend.jwks_url()


def test_user_data_survives_key_rotation(backend, realm):
    """
    A key rotated in after the key set was cached verifies on first use.

    The first token populates the cache, the second reuses it, and the token
    signed by the new key misses the cache and forces an immediate refetch.
    """
    _, keys, requests = realm
    old_private, old_jwk = _signing_key("old")
    keys.append(old_jwk)
    for _ in range(2):
        user = backend.user_data(_access_token(old_private, "old"))
        assert user["preferred_username"] == "jdoe"
    assert len(requests) == 1

    new_private, new_jwk = _signing_key("new")
    keys.append(new_jwk)
    user = backend.user_data(_access_token(new_private, "new"))
    assert user["preferred_username"] == "jdoe"
    assert requests == [f"{REALM_PATH}/protocol/openid-connect/certs"] * 2


@pytest.mark.parametrize(
    ("kid", "signed_by_realm", "audience"),
    [
        ("unknown", False, CLIENT_ID),  # signed by a key the realm doesn't publish
        ("realm", False, CLIENT_ID),  # claims a published kid, signed by another key
        ("realm", True, "other"),  # issued to another client in the realm
    ],
)
def test_user_data_rejects_bad_tokens(backend, realm, kid, signed_by_realm, audience):
    """Invalid tokens raise AuthTokenError rather than a bare PyJWT error"""
    _, keys, _ = realm
    realm_private, realm_jwk = _signing_key("realm")
    keys.append(realm_jwk)
    private_key = realm_private if signed_by_realm else _signing_key("x")[0]
    with pytest.raises(AuthTokenError):
        backend.user_data(_access_token(private_key, kid, audience=audience))


def test_user_data_rejects_malformed_token(backend):
    """A malformed token raises AuthTokenError"""
    with pytest.raises(AuthTokenError):
        backend.user_data("not-a-jwt")
