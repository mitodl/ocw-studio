"""Content sync apps"""
from django.apps import AppConfig


class ContentSyncApp(AppConfig):
    """App for content_sync"""

    name = "content_sync"

    def ready(self):
        """Application is ready"""
        import content_sync.signals  # noqa: F401
