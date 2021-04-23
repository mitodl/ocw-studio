""" Sync abstract base """
import abc
from typing import Any

from content_sync.models import ContentSyncState
from websites.models import Website


class BaseSyncBackend(abc.ABC):
    """ Base class for syncing backends """

    # NOTE: concrete implementations of this will probably want to
    #       initialize a client object for the backing service (e.g. ghapi)
    def __init__(self, website: Website):
        self.website = website

    @abc.abstractmethod
    def create_website_in_backend(self):  # pragma: no cover
        """
        Called to create the website in the backend.

        An example would be creating a VCS repository.
        """
        ...

    @abc.abstractmethod
    def create_backend_preview(self):  # pragma: no cover
        """
        Called to create a site preview in the backend.

        An example would be merging the latest commits into a VCS' preview branch.
        """
        ...

    @abc.abstractmethod
    def create_backend_release(self):  # pragma: no cover
        """
        Called to create a site release in the backend.

        An example would be merging the latest commits into a VCS' release branch.
        """
        ...

    # NOTE: these next two could perform the same operations if the backing service
    #       supports an UPSERT type operation (GitHub does)
    @abc.abstractmethod
    def create_content_in_backend(
        self, sync_state: ContentSyncState
    ):  # pragma: no cover
        """
        Called to create a piece of content in the backend.

        An example would be commiting the contents of the WebsiteContent to the VCS repository.
        """
        ...

    @abc.abstractmethod
    def update_content_in_backend(
        self, sync_state: ContentSyncState
    ):  # pragma: no cover
        """
        Called to create a piece of content in the backend.

        An example would be commiting the updated contents of the WebsiteContent to the VCS repository.
        """
        ...

    @abc.abstractmethod
    def delete_content_in_backend(
        self, sync_state: ContentSyncState
    ):  # pragma: no cover
        """
        Called to delete a piece of content in the backend.

        An example would be making a commit to delete content in the VCS repository.
        """
        ...

    # NOTE: This will be fired for every piece of content that is created, changed, or deleted in the database
    #       See content_sync/signals.py for details.
    def sync_content_to_backend(self, sync_state: ContentSyncState):
        """ Sync a given piece of content given its ContentSyncState """
        if not sync_state.synced_checksum:
            self.create_content_in_backend(sync_state)
        elif sync_state.content.deleted:
            self.delete_content_in_backend(sync_state)
        else:
            self.update_content_in_backend(sync_state)

    def sync_all_content_to_backend(self):
        """ Sync all content for the website """
        for sync_state in ContentSyncState.objects.filter(
            content__website=self.website
        ):
            self.sync_content_to_backend(sync_state)

    @abc.abstractmethod
    def create_content_in_db(self, data: Any):  # pragma: no cover
        """
        Called to create a piece of content in the database.

        An example would be taking a VCS commit/file object and writing it to the database.
        """
        ...

    @abc.abstractmethod
    def update_content_in_db(self, data: Any):  # pragma: no cover
        """
        Called to update a piece of content in the database.

        An example would be taking a VCS commit/file object and writing the updates to the database.
        """
        ...

    @abc.abstractmethod
    def delete_content_in_db(self, data: Any):  # pragma: no cover
        """
        Called to create a piece of content in the database.

        An example would be deleting the content from the database if it doesn't exist in the VCS repository.
        """
        ...

    @abc.abstractmethod
    def sync_all_content_to_db(self):  # pragma: no cover
        """
        Sync all content from the backend to the application database.

        An example would be walking content in the VCS repository
        and creating/updating/deleting corresponding WebsiteContent/ContentSyncState
        records in the database.
        """
        ...
