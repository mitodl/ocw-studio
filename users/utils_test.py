"""Tests for user utils"""
import pytest

from users.factories import UserFactory
from users.utils import format_recipient


@pytest.mark.parametrize(
    ("name", "email", "expected"),
    [
        [  # noqa: PT007
            "Mr. John Thornton",
            "jthornton@test.edu",
            '"Mr. John Thornton" <jthornton@test.edu>',
        ],
        [  # noqa: PT007
            "John Thornton",
            "jthornton@test.com",
            "John Thornton <jthornton@test.com>",
        ],
        [  # noqa: PT007
            "Joanne O'Brien",
            "jobrien@test.edu",
            "Joanne O'Brien <jobrien@test.edu>",
        ],
        [  # noqa: PT007
            "Cpl. Joanne O'Brien",
            "jobrien@test.edu",
            '"Cpl. Joanne O\'Brien" <jobrien@test.edu>',
        ],
    ],
)
def test_format_recipient(name, email, expected):
    """format_recipient should return the expected string"""
    user = UserFactory.build(name=name, email=email)
    assert format_recipient(user) == expected
