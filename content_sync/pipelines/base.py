""" Sync abstract base """
import abc
from typing import Optional

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.utils import check_mandatory_settings
from websites.models import Website


class BasePipeline(abc.ABC):
    """ Base class for a pipeline """

    @staticmethod
    @abc.abstractmethod
    def get_api():
        """Get a pipeline API instance"""
        ...

    @abc.abstractmethod
    def get_build_status(self, build_id: int):
        """Retrieve the status of the build"""
        ...

    @abc.abstractmethod
    def abort_build(self, build_id: int):
        """Abort a build"""
        ...


class BaseSyncPipeline(BasePipeline):
    """ Base class for preview/publish pipelines """

    MANDATORY_SETTINGS = []
    VERSION_LIVE = VERSION_LIVE
    VERSION_DRAFT = VERSION_DRAFT

    def __init__(self, website: Website, api: Optional[object] = None):
        if self.MANDATORY_SETTINGS:
            check_mandatory_settings(self.MANDATORY_SETTINGS)
        self.api = api or self.__class__.get_api()
        self.website = website

    @abc.abstractmethod
    def upsert_website_pipeline(self):  # pragma: no cover
        """
        Called to create/update the website pipeline.
        """
        ...

    @abc.abstractmethod
    def trigger_pipeline_build(self, version: str) -> int:
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


class BaseThemeAssetsPipeline(BasePipeline):
    """ Base class for theme assets pipeline """

    def __init__(self, api: Optional[object] = None):
        if self.MANDATORY_SETTINGS:
            check_mandatory_settings(self.MANDATORY_SETTINGS)
        self.api = api or self.__class__.get_api()

    @abc.abstractmethod
    def trigger_pipeline_build(self) -> int:
        """
        Called to trigger the website pipeline.
        """
        ...

    @abc.abstractmethod
    def unpause_pipeline(self):
        """
        Called to unpause a website pipeline.
        """
        ...
