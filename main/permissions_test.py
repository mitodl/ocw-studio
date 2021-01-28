"""Tests for permissions"""
import pytest
from django.contrib.auth.models import AnonymousUser

from main.permissions import ReadonlyPermission


@pytest.mark.parametrize(
    "method,result",
    [("GET", True), ("HEAD", True), ("OPTIONS", True), ("POST", False), ("PUT", False)],
)
def test_anonymous_readonly(mocker, method, result):
    """
    Test that anonymous users are allowed for readonly verbs
    """
    perm = ReadonlyPermission()
    request = mocker.Mock(user=AnonymousUser(), method=method)
    assert perm.has_permission(request, mocker.Mock()) is result
