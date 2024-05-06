from django.utils import timezone

from external_resources import api
from external_resources.exceptions import CheckFailedError
from external_resources.models import ExternalResourceState
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.models import WebsiteContent


def check_external_resources_for_breakages():
    """Check external resources for broken links."""
    external_resources = WebsiteContent.objects.filter(
        type=CONTENT_TYPE_EXTERNAL_RESOURCE
    ).select_related("external_resource_state")

    for resource in external_resources:
        try:
            state = resource.external_resource_state
        except ExternalResourceState.DoesNotExist:
            state = ExternalResourceState(
                content=resource,
            )

        try:
            is_url_broken, url_status = api.is_external_url_broken(resource)
            state.external_url_response_code = url_status
            state.is_external_url_broken = is_url_broken

            is_backup_url_broken, backup_url_status = api.is_backup_url_broken(resource)
            state.backup_url_response_code = backup_url_status
            state.is_backup_url_broken = is_backup_url_broken
        except CheckFailedError:
            state.status = ExternalResourceState.Status.CHECK_FAILED
        else:
            if is_url_broken and is_backup_url_broken:
                # Neither external_url nor backup_url are valid.
                state.status = ExternalResourceState.Status.BROKEN
            else:
                # Either external_url or backup_url is valid.
                state.status = ExternalResourceState.Status.VALID

            if is_url_broken and not resource.metadata.get("is_broken", False):
                resource.metadata["is_broken"] = True
                resource.save()
        finally:
            state.last_checked = timezone.now()

        state.save()
