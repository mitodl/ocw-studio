"""
Validate that our settings functions work
"""

import importlib
import os
import sys
from unittest import mock

import pytest
import semantic_version
from django.conf import settings
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django_redis import get_redis_connection
from mitol.common import envs

# from mitol.common import envs, pytest_utils  # noqa: ERA001


REQUIRED_SETTINGS = {
    "MAILGUN_SENDER_DOMAIN": "mailgun.fake.domain",
    "MAILGUN_KEY": "fake_mailgun_key",
    "OCW_STUDIO_BASE_URL": "http://localhost:8053",
}


# TODO: Figure out why this test now always fails because it thinks app.json has been modified #pylint: disable=fixme  # noqa: FIX002, TD002, TD003
# test_app_json_modified = pytest_utils.test_app_json_modified  # noqa: ERA001


def cleanup_settings():
    """Cleanup settings after a test"""
    envs.env.reload()
    importlib.reload(sys.modules["mitol.common.settings.base"])
    importlib.reload(sys.modules["mitol.common.settings.webpack"])
    importlib.reload(sys.modules["mitol.mail.settings.email"])
    importlib.reload(sys.modules["mitol.authentication.settings.touchstone"])


class TestSettings(TestCase):
    """Validate that settings work as expected."""

    def patch_settings(self, values):
        """Patch the cached settings loaded by EnvParser"""
        with mock.patch.dict("os.environ", values, clear=True):
            os.environ["DJANGO_SETTINGS_MODULE"] = "main.settings"
            envs.env.reload()
            return self.reload_settings()

    def reload_settings(self):
        """
        Reload settings module with cleanup to restore it.

        Returns:
            dict: dictionary of the newly reloaded settings ``vars``
        """
        # Restore settings to original settings after test
        self.addCleanup(cleanup_settings)
        return vars(sys.modules["main.settings"])

    def test_s3_settings(self):
        """Verify that we enable and configure S3 with a variable"""
        # Unset, we don't do S3
        settings_vars = self.patch_settings(
            {**REQUIRED_SETTINGS, "OCW_STUDIO_USE_S3": "False"}
        )
        assert (
            settings_vars.get("DEFAULT_FILE_STORAGE")
            != "storages.backends.s3boto3.S3Boto3Storage"
        )

        with pytest.raises(ImproperlyConfigured):
            self.patch_settings({"OCW_STUDIO_USE_S3": "True"})

        # Verify it all works with it enabled and configured 'properly'
        settings_vars = self.patch_settings(
            {
                **REQUIRED_SETTINGS,
                "OCW_STUDIO_USE_S3": "True",
                "AWS_ACCESS_KEY_ID": "1",
                "AWS_SECRET_ACCESS_KEY": "2",
                "AWS_STORAGE_BUCKET_NAME": "3",
            }
        )
        assert (
            settings_vars.get("DEFAULT_FILE_STORAGE")
            == "storages.backends.s3boto3.S3Boto3Storage"
        )

    def test_admin_settings(self):
        """Verify that we configure email with environment variable"""

        settings_vars = self.patch_settings(
            {**REQUIRED_SETTINGS, "OCW_STUDIO_ADMIN_EMAIL": ""}
        )
        assert not settings_vars.get("ADMINS", False)

        test_admin_email = "cuddle_bunnies@example.com"
        settings_vars = self.patch_settings(
            {**REQUIRED_SETTINGS, "OCW_STUDIO_ADMIN_EMAIL": test_admin_email}
        )
        assert (("Admins", test_admin_email),) == settings_vars["ADMINS"]

        # Manually set ADMIN to our test setting and verify e-mail
        # goes where we expect
        settings.ADMINS = (("Admins", test_admin_email),)
        mail.mail_admins("Test", "message")
        assert test_admin_email in mail.outbox[0].to

    def test_db_ssl_enable(self):
        """Verify that we can enable/disable database SSL with a var"""

        # Check default state is SSL on
        settings_vars = self.patch_settings(REQUIRED_SETTINGS)
        assert settings_vars["DATABASES"]["default"]["OPTIONS"] == {
            "sslmode": "require"
        }

        # Check enabling the setting explicitly
        settings_vars = self.patch_settings(
            {**REQUIRED_SETTINGS, "OCW_STUDIO_DB_DISABLE_SSL": "True"}
        )
        assert settings_vars["DATABASES"]["default"]["OPTIONS"] == {}

        # Disable it
        settings_vars = self.patch_settings(
            {**REQUIRED_SETTINGS, "OCW_STUDIO_DB_DISABLE_SSL": "False"}
        )
        assert settings_vars["DATABASES"]["default"]["OPTIONS"] == {
            "sslmode": "require"
        }

    @staticmethod
    def test_semantic_version():
        """
        Verify that we have a semantic compatible version.
        """
        semantic_version.Version(settings.VERSION)

    def test_server_side_cursors_disabled(self):
        """DISABLE_SERVER_SIDE_CURSORS should be true by default"""
        settings_vars = self.patch_settings(REQUIRED_SETTINGS)
        assert (
            settings_vars["DEFAULT_DATABASE_CONFIG"]["DISABLE_SERVER_SIDE_CURSORS"]
            is True
        )

    def test_server_side_cursors_enabled(self):
        """DISABLE_SERVER_SIDE_CURSORS should be false if ocw_studio_DB_DISABLE_SS_CURSORS is false"""
        settings_vars = self.patch_settings(
            {**REQUIRED_SETTINGS, "OCW_STUDIO_DB_DISABLE_SS_CURSORS": "False"}
        )
        assert (
            settings_vars["DEFAULT_DATABASE_CONFIG"]["DISABLE_SERVER_SIDE_CURSORS"]
            is False
        )

    def test_redis_max_connections(self):
        """Max connections for redis pool should be set to the default"""
        r = get_redis_connection("redis")
        assert r.connection_pool.max_connections == settings.REDIS_MAX_CONNECTIONS
