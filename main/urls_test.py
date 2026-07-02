"""Tests for URLs"""

from unittest import TestCase

import pytest
from django.urls import resolve, reverse
from health_check.views import HealthCheckView


class URLTests(TestCase):
    """URL tests"""

    def test_urls(self):
        """Make sure URLs match with resolved names"""
        assert reverse("main-index") == "/"


@pytest.mark.parametrize(
    "path",
    [
        "/health/startup/",
        "/health/liveness/",
        "/health/readiness/",
        "/health/full/",
    ],
)
def test_healthcheck_urls_resolve(path):
    """Healthcheck subset URLs should resolve to HealthCheckView"""
    match = resolve(path)
    assert match.func.view_class == HealthCheckView
