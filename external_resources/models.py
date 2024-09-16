"""External Resources models"""

from bulk_update_or_create import BulkUpdateOrCreateQuerySet
from django.db import models
from mitol.common.models import TimestampedModel

from websites.models import WebsiteContent


class ExternalResourceState(TimestampedModel):
    """Data model for tracking the state of external resources"""

    class WaybackStatus(models.TextChoices):
        """Choices for Wayback Machine Status"""

        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        ERROR = "error", "Error"
        IN_PROGRESS = "in_progress", "In Progress"

    objects = BulkUpdateOrCreateQuerySet.as_manager()

    content = models.OneToOneField(
        WebsiteContent,
        on_delete=models.CASCADE,
        related_name="external_resource_state",
    )

    wayback_status = models.CharField(
        max_length=16,
        choices=WaybackStatus.choices,
        default=WaybackStatus.PENDING,
        help_text="The status of the Wayback Machine archiving job.",
    )

    wayback_job_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="The ID of the Wayback Machine job for archiving the resource.",
    )

    wayback_url = models.URLField(
        blank=True,
        help_text="The Wayback Machine URL for this resource.",
    )

    external_url_response_code = models.IntegerField(
        default=None,
        null=True,
        blank=True,
    )

    last_checked = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        help_text="The last time when this resource was checked for breakages.",
    )

    def __str__(self):
        """Return a string representation of the state"""
        name = self.content.title if self.content else None
        return f"State for external resource: {name}"
