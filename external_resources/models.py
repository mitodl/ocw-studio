"""External Resources models"""

from bulk_update_or_create import BulkUpdateOrCreateQuerySet
from django.db import models
from mitol.common.models import TimestampedModel

from websites.models import WebsiteContent


class ExternalResourceState(TimestampedModel):
    """Data model for tracking the state of external resources"""

    class Status(models.TextChoices):
        """Choices for External Resource Status"""

        UNCHECKED = "unchecked", "Unchecked or pending check"
        VALID = "valid", "External Resource URL is valid"
        BROKEN = "broken", "External Resource URL is broken"
        CHECK_FAILED = (
            "check_failed",
            "Last attempt to check the External Resource URL failed",
        )

    class WaybackStatus(models.TextChoices):
        """Choices for Wayback Machine Status"""

        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"

    objects = BulkUpdateOrCreateQuerySet.as_manager()

    content = models.OneToOneField(
        WebsiteContent,
        on_delete=models.CASCADE,
        related_name="external_resource_state",
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.UNCHECKED,
        help_text="Status of the external resource (valid, broken, etc.).",
    )

    last_checked = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        help_text="The last time when this resource was checked for breakages.",
    )

    external_url_response_code = models.IntegerField(
        default=None,
        null=True,
        blank=True,
    )

    wayback_job_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Job ID returned by Wayback Machine API when submitting URL for snapshot.",  # noqa: E501
    )

    wayback_status = models.CharField(
        max_length=16,
        choices=WaybackStatus.choices,
        default="",
        blank=True,
        help_text="The status of the Wayback Machine snapshot taken from archiving job.",  # noqa: E501
    )

    wayback_url = models.URLField(
        blank=True,
        help_text="URL of the Wayback Machine snapshot.",
    )

    def __str__(self):
        """Return a string representation of the state"""
        name = self.content.title if self.content else None
        return f"State for external resource: {name}"
