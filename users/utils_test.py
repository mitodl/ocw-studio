"""Tests for user utils"""
from users.factories import UserFactory
from users.utils import format_recipient


def test_format_recipient():
    """format_recipient should return the expected string"""
    user = UserFactory.build()
    assert format_recipient(user) == f'"{user.email}" <{user.email}>'
