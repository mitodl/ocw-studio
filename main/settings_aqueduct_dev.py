"""Opt-in django-aqueduct settings module for local development.

Same as ``main/settings_aqueduct.py``, but uses :class:`DevAqueductSettings`
so that any values missing from the environment/.env file are filled in
from Vault via OIDC. Select via
``DJANGO_SETTINGS_MODULE=main.settings_aqueduct_dev``.
``main/settings.py`` is untouched and remains the default settings module
used everywhere else.
"""

from django_aqueduct import configure_django_settings

from main.aqueduct_settings import DevAqueductSettings

configure_django_settings(DevAqueductSettings)
