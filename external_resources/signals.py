import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from external_resources.models import ExternalResourceState
from external_resources.tasks import submit_url_to_wayback_task
from main import settings
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.models import WebsiteContent

log = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=WebsiteContent,
    dispatch_uid="external_resource_state_website_content_upsert",
)
def upsert_external_resource_state(
    sender,  # noqa: ARG001
    instance,
    created,  # noqa: ARG001
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """Create/update the external resource state"""
    if instance.type == CONTENT_TYPE_EXTERNAL_RESOURCE:
        state_exists = ExternalResourceState.objects.filter(content=instance).exists()
        if not state_exists:
            defaults = {
                "status": ExternalResourceState.Status.UNCHECKED,
                "last_checked": None,
                "external_url_response_code": None,
                "wayback_job_id": "",
                "wayback_url": "",
                "wayback_status": "",
                "wayback_status_ext": "",
                "wayback_http_status": None,
                "wayback_last_successful_submission": None,
            }
            ExternalResourceState.objects.update_or_create(
                content=instance, defaults=defaults
            )
            if settings.ENABLE_WAYBACK_TASKS:
                submit_url_to_wayback_task.delay(instance.id)
                log.info(
                    "New external resource created: %s. Submitting to Wayback Machine.",
                    instance.title,
                )
                log.debug(
                    "Created ExternalResourceState for WebsiteContent id=%s",
                    instance.id,
                )
