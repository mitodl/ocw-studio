"""Opt-in django-aqueduct settings module for ocw-studio.

Select this module explicitly via ``DJANGO_SETTINGS_MODULE=main.settings_aqueduct``.
``main/settings.py`` is untouched and remains the default settings module
used everywhere else.
"""

from django_aqueduct import configure_django_settings

from main.aqueduct_settings import AqueductSettings

configure_django_settings(AqueductSettings)
