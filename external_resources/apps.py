"""External Resources Apps"""

from django.apps import AppConfig


class ExternalResourcesConfig(AppConfig):
    """App for External Resources"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "external_resources"

    def ready(self):
        """Application is ready"""
        import external_resources.signals  # noqa: F401
