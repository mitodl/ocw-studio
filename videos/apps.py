"""video apps"""

from django.apps import AppConfig


class VideoApp(AppConfig):
    """App for video"""

    name = "videos"

    def ready(self):
        """Application is ready"""
        import videos.signals  # noqa: F401
