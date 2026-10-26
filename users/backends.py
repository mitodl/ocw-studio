"""Social auth backends"""

from functools import cache

import jwt
from social_core.backends.keycloak import KeycloakOAuth2
from social_core.exceptions import AuthTokenError

KEYCLOAK_TOKEN_PATH = "/protocol/openid-connect/token"  # noqa: S105
KEYCLOAK_CERTS_PATH = "/protocol/openid-connect/certs"


@cache
def _jwks_client(jwks_url):
    """Return a per-process JWKS client, which caches the key set for 5 minutes"""
    return jwt.PyJWKClient(jwks_url)


class KeycloakJWKSOAuth2(KeycloakOAuth2):
    """
    KeycloakOAuth2, but verifying the access token against the realm JWKS.

    The upstream backend checks the signature against a static PUBLIC_KEY
    setting, so rotating the realm signing key breaks login until that setting
    is redeployed. This looks the key up by the token's kid instead.
    """

    def jwks_url(self):
        """Derive the realm JWKS URL from the token endpoint"""
        token_url = self.access_token_url()
        if not token_url.endswith(KEYCLOAK_TOKEN_PATH):
            msg = f"ACCESS_TOKEN_URL must end in {KEYCLOAK_TOKEN_PATH}: {token_url}"
            raise ValueError(msg)
        return token_url.removesuffix(KEYCLOAK_TOKEN_PATH) + KEYCLOAK_CERTS_PATH

    def user_data(self, access_token, *args, **kwargs):  # noqa: ARG002
        """Decode user data from the access token"""
        try:
            signing_key = _jwks_client(self.jwks_url()).get_signing_key_from_jwt(
                access_token
            )
            return jwt.decode(
                access_token,
                key=signing_key.key,
                algorithms=[self.algorithm()],
                audience=self.audience(),
                leeway=self.setting("JWT_LEEWAY", default=0),
            )
        except jwt.PyJWTError as error:
            raise AuthTokenError(self, error) from error
