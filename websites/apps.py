"""Websites app definition"""
from django.apps import AppConfig


class WebsitesConfig(AppConfig):
    """AppConfig for websites"""

    name = "websites"

    def ready(self):
        """Application is ready"""
        import websites.signals  # pylint:disable=unused-import, import-outside-toplevel
