""" Sync abstract base """
import abc

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from websites.models import Website


class BaseSyncPipeline(abc.ABC):
    """ Base class for preview/publish pipelines """

    MANDATORY_SETTINGS = []
    VERSION_LIVE = "live"
    VERSION_DRAFT = "draft"

    def __init__(self, website: Website):
        """Make sure all required settings are present"""
        missing_settings = []
        for setting_name in self.MANDATORY_SETTINGS:
            if getattr(settings, setting_name, None) in (
                None,
                "",
            ):
                missing_settings.append(setting_name)
        if missing_settings:
            raise ImproperlyConfigured(
                "The following settings are missing: {}".format(
                    ", ".join(missing_settings)
                )
            )
        self.website = website

    @abc.abstractmethod
    def upsert_website_pipeline(self):  # pragma: no cover
        """
        Called to create/update the website pipeline.
        """
        ...

    @abc.abstractmethod
    def trigger_pipeline_build(self, version: str):
        """
        Called to trigger the website pipeline.
        """
        ...

    @abc.abstractmethod
    def unpause_pipeline(self, version: str):
        """
        Called to unpause a website pipeline.
        """
        ...
