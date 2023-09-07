"""Sync abstract base"""
import abc


class BasePipelineApi(abc.ABC):
    """Base class for a pipeline API"""

    @abc.abstractmethod
    def list_pipelines(self, names: list[str] | None = None):
        """Retrieve a list of pipelines"""
        ...

    @abc.abstractmethod
    def delete_pipelines(self, names: list[str] | None = None):
        """Delete a list of pipelines"""
        ...


class BasePipeline(abc.ABC):
    """Base class for a pipeline"""

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

    @abc.abstractmethod
    def upsert_pipeline(self):  # pragma: no cover
        """
        Called to create/update the pipeline.
        """  # noqa: D401
        ...

    @abc.abstractmethod
    def trigger_pipeline_build(self, pipeline_name: str) -> int:
        """
        Called to trigger the website pipeline.
        """  # noqa: D401
        ...

    @abc.abstractmethod
    def unpause_pipeline(self, pipeline_name: str):
        """
        Called to unpause a website pipeline.
        """  # noqa: D401
        ...

    @abc.abstractmethod
    def pause_pipeline(self, pipeline_name: str):
        """
        Called to pause a website pipeline.
        """  # noqa: D401
        ...


class BaseGeneralPipeline(BasePipeline):
    """Base class for general pipelines"""


class BaseSitePipeline(BasePipeline):
    """Base class for site-specific publishing"""


class BaseMassBuildSitesPipeline(BasePipeline):
    """Base class for mass site building"""

    PIPELINE_NAME = "mass-build-sites"


class BaseThemeAssetsPipeline(BasePipeline):
    """Base class for theme asset publishing"""

    PIPELINE_NAME = "ocw-theme-assets"


class BaseUnpublishedSiteRemovalPipeline(BasePipeline):
    """Base class for removing unpublished sites"""

    PIPELINE_NAME = "remove-unpublished-sites"
