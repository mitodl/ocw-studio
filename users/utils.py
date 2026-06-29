"""Utils for users"""

from email.utils import formataddr
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from users.models import User


def format_recipient(user: User) -> str:
    """
    Format a user as a recipient for an email
    """
    return formataddr((f"{user.name}", user.email))
