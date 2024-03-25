"""Content sync models"""

from bulk_update_or_create import BulkUpdateOrCreateQuerySet
from django.db import models
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet

from websites.models import WebsiteContent


class ContentSyncStateQuerySet(TimestampedModelQuerySet):
    """Queryset for ContentSyncState"""


class ContentSyncState(TimestampedModel):
    """Data model for tracking the sync state of website content"""

    objects = BulkUpdateOrCreateQuerySet.as_manager()

    content = models.OneToOneField(
        WebsiteContent,
        on_delete=models.CASCADE,
        related_name="content_sync_state",
    )
    current_checksum = models.CharField(max_length=64)  # sized for a sha256
    synced_checksum = models.CharField(  # noqa: DJ001
        max_length=64, null=True
    )  # sized for a sha256

    data = models.JSONField(
        null=True
    )  # used to store arbitrary state data between syncs (e.g. current blob sha for git)  # noqa: E501

    @property
    def is_synced(self) -> bool:
        """Returns True if the content is up-to-date"""
        return self.current_checksum == self.synced_checksum

    def __str__(self):  # pragma: no cover
        """Returns a string representation of the state"""  # noqa: D401
        return f"Sync State for content: {self.content.title if self.content else None}"
