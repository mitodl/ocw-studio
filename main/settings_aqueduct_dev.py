"""Opt-in django-aqueduct settings module for local development.

Same as ``main/settings_aqueduct.py``, but uses :class:`DevAqueductSettings`
so that any values missing from the environment/.env file are filled in from
Vault. The Vault source is configured from ``VAULT_*`` environment variables
(``VAULT_ADDR``, ``VAULT_PATH``, ``VAULT_MOUNT``, ``VAULT_AUTH_METHOD``,
``VAULT_ROLE``); without ``VAULT_ADDR`` it runs Vault-less. Select via
``DJANGO_SETTINGS_MODULE=main.settings_aqueduct_dev``.
``main/settings.py`` is untouched and remains the default settings module
used everywhere else.
"""

from django_aqueduct import configure_django_settings

from main.aqueduct_settings import DevAqueductSettings, init_sentry_from_model

configure_django_settings(DevAqueductSettings, pre_configure=init_sentry_from_model)
