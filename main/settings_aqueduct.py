"""Opt-in django-aqueduct settings module for ocw-studio.

Select this module explicitly via ``DJANGO_SETTINGS_MODULE=main.settings_aqueduct``.
``main/settings.py`` is untouched and remains the default settings module
used everywhere else.

Sentry is initialised through the ``pre_configure`` hook so it runs against
the validated model *before* settings are injected — the same "capture config
errors as early as possible" ordering main/settings.py uses.
"""

from django_aqueduct import configure_django_settings

from main.aqueduct_settings import AqueductSettings, init_sentry_from_model

configure_django_settings(AqueductSettings, pre_configure=init_sentry_from_model)
