"""Tests for the Celery app configuration"""

from celery.signals import setup_logging
from mitol.observability import logging as observability_logging

# Importing the module connects its signal receivers
import main.celery  # noqa: F401


def test_setup_logging_keeps_structlog(mocker):
    """The worker reapplies structlog, so Celery leaves the root logger alone"""
    mock_configure = mocker.patch.object(observability_logging, "configure_structlog")

    receivers = setup_logging.send(
        sender=None, loglevel="INFO", logfile=None, format="", colorize=False
    )

    assert receivers
    mock_configure.assert_called_once_with(force=True)
