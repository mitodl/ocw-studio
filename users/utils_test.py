"""Tests for user utils"""
from users.factories import UserFactory
from users.utils import format_recipient


def test_format_recipient():
    user = UserFactory.build()
    assert format_recipient(user) == f'"{user.email}" <{user.email}>'
