""" gdrive_sync apps """
from django.apps import AppConfig


class GDriveSyncApp(AppConfig):
    """ App for gdrive_sync """

    name = "gdrive_sync"

    def ready(self):
        """ Application is ready """
        import gdrive_sync.signals  # pylint:disable=unused-import, import-outside-toplevel
