"""Backfill the Keycloak `sub` claim into UserSocialAuth.extra_data."""

import base64
import binascii
import json
import logging

from django.core.paginator import Paginator
from django.db import migrations

log = logging.getLogger(__name__)

PROVIDER = "keycloak"
JWT_SEGMENTS = 3

# KeycloakJWKSOAuth2 authenticates the user from the access token, so its
# subject is the authoritative one. The ID token is a fallback: Keycloak only
# adds `sub` to the access token through the "basic" client scope, so a client
# whose default scopes were replaced by an explicit list can be missing it.
TOKEN_FIELDS = ("access_token", "id_token")


def chunked_iterator(queryset):
    """Chunked iteration over a queryset to avoid loading it all into memory"""
    paginator = Paginator(queryset, 100)
    for page in range(1, paginator.num_pages + 1):
        yield from paginator.page(page).object_list


def jwt_claims(token):
    """
    Return a stored JWT's claims, or None if they cannot be read.

    The signature is deliberately not checked. These tokens were verified when
    social-auth stored them during a previous successful login, and by now they
    are expired and may have been signed by a rotated realm key, so re-verifying
    is neither possible nor meaningful.
    """
    if not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != JWT_SEGMENTS:
        return None
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except binascii.Error, ValueError:
        return None
    return claims if isinstance(claims, dict) else None


def token_subject(extra_data):
    """Return the `sub` claim from the first stored token that carries one"""
    for field in TOKEN_FIELDS:
        claims = jwt_claims(extra_data.get(field))
        subject = (claims or {}).get("sub")
        if isinstance(subject, str) and subject:
            return subject
    return None


def backfill_keycloak_sub(apps, schema_editor):
    """
    Record each Keycloak association's subject so social-core 6 can migrate it.

    social-core 6 keys Keycloak accounts on the immutable `sub` instead of the
    mutable `username`, and migrates an existing association only when the row
    already carries a `sub` matching the one presented at login. Associations
    created before 6.0 have no such value -- the backend defined no EXTRA_DATA
    entry for it -- so without this every pre-existing user is locked out with
    AuthAssociationError. Reading it back out of the tokens we already stored
    supplies that evidence, which social-core then verifies as usual.
    """
    user_social_auth = apps.get_model("social_django", "UserSocialAuth")
    rows = user_social_auth.objects.filter(provider=PROVIDER).order_by("id")

    updated = []
    skipped = 0
    for social in chunked_iterator(rows):
        extra_data = social.extra_data
        if not isinstance(extra_data, dict) or extra_data.get("sub"):
            continue
        subject = token_subject(extra_data)
        if subject is None:
            skipped += 1
            continue
        social.extra_data = {**extra_data, "sub": subject}
        updated.append(social)

    if updated:
        user_social_auth.objects.bulk_update(updated, ["extra_data"], batch_size=100)

    log.info(
        "Backfilled Keycloak sub for %d association(s); %d had no usable token",
        len(updated),
        skipped,
    )


class Migration(migrations.Migration):
    """Backfill Keycloak subjects before social-core 6 needs them"""

    dependencies = [
        ("users", "0002_users_active_default"),
        ("social_django", "0020_backfill_id_keys"),
    ]

    operations = [
        migrations.RunPython(backfill_keycloak_sub, migrations.RunPython.noop)
    ]
