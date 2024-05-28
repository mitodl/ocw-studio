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
        VALID = "valid", "Either URL or backup URL is valid"
        BROKEN = "broken", "Both URL and backup URL are broken"
        CHECK_FAILED = (
            "check_failed",
            "Last attempt to check the resource failed unexpectedly",
        )

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
        help_text="The status of this external resource.",
    )

    external_url_response_code = models.IntegerField(
        default=None,
        null=True,
        blank=True,
    )

    backup_url_response_code = models.IntegerField(
        default=None,
        null=True,
        blank=True,
    )

    is_external_url_broken = models.BooleanField(
        default=None,
        null=True,
        blank=True,
    )

    is_backup_url_broken = models.BooleanField(
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
