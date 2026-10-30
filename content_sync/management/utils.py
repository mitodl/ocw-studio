"""Helpers for content sync management commands."""  # noqa: INP001

from django.core.management import CommandError

from users.models import User


def get_commit_user(email: str) -> User:
    """Resolve the active Studio user responsible for a manual sync."""
    try:
        return User.objects.get(email=email, is_active=True)
    except User.DoesNotExist as exc:
        msg = "--user must be the email address of an existing active Studio user."
        raise CommandError(msg) from exc
