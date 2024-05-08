import celery
from django.utils import timezone
from mitol.common.utils import chunks

from external_resources import api
from external_resources.exceptions import CheckFailedError
from external_resources.models import ExternalResourceState
from main.celery import app
from websites.constants import (
    BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK,
    CONTENT_TYPE_EXTERNAL_RESOURCE,
)
from websites.models import WebsiteContent


@app.task(acks_late=True, rate_limit="100/s", priority=-1)
def check_external_resources(resources: list[str]):
    """Check external resources for broken links"""

    for resource in resources:
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

            # If url is broken, check backup url for the resource
            is_backup_url_broken, backup_url_status = api.is_backup_url_broken(resource)
            state.backup_url_response_code = backup_url_status
            state.is_backup_url_broken = is_backup_url_broken
        except CheckFailedError:
            state.status = ExternalResourceState.Status.CHECK_FAILED
        else:
            if (
                url_status not in api.STATUS_CODE_WHITELIST
                or backup_url_status not in api.STATUS_CODE_WHITELIST
            ):
                if is_url_broken and is_backup_url_broken:
                    # both external_url and backup_url are broken.
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


@app.task(bind=True, acks_late=True)
def check_external_resources_for_breakages(self):
    """Check external resources for broken links."""
    external_resources = WebsiteContent.objects.filter(
        type=CONTENT_TYPE_EXTERNAL_RESOURCE
    ).select_related("external_resource_state")

    tasks = [
        check_external_resources.s(resources)
        for resources in chunks(
            external_resources, chunk_size=BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK
        )
    ]
    raise self.replace(celery.group(tasks))
