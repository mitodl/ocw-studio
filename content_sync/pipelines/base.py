""" Sync abstract base """
import abc


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

    @abc.abstractmethod
    def trigger_pipeline_build(self, team: str, pipeline_name: str) -> int:
        """
        Called to trigger the website pipeline.
        """
        ...

    @abc.abstractmethod
    def unpause_pipeline(self, pipeline_name: str):
        """
        Called to unpause a website pipeline.
        """
        ...
