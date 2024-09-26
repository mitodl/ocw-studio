"""External Resources Tasks"""

import logging

import celery
from django.utils import timezone
from mitol.common.utils import chunks

from external_resources import api
from external_resources.constants import (
    EXTERNAL_RESOURCE_TASK_PRIORITY,
    EXTERNAL_RESOURCE_TASK_RATE_LIMIT,
    METADATA_URL_STATUS_CODE,
    RESOURCE_UNCHECKED_STATUSES,
)
from external_resources.exceptions import CheckFailedError
from external_resources.models import ExternalResourceState
from main.celery import app
from websites.constants import (
    BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK,
    CONTENT_TYPE_EXTERNAL_RESOURCE,
)
from websites.models import WebsiteContent

log = logging.getLogger()


@app.task(
    acks_late=True,
    rate_limit=EXTERNAL_RESOURCE_TASK_RATE_LIMIT,
    priority=EXTERNAL_RESOURCE_TASK_PRIORITY,
)
def check_external_resources(resources: list[int]):
    """Check external resources for broken links"""

    resources = WebsiteContent.objects.filter(id__in=resources).select_related(
        "external_resource_state"
    )

    for resource in resources:
        try:
            state = resource.external_resource_state
        except ExternalResourceState.DoesNotExist as ex:
            log.debug(ex)
            state = ExternalResourceState(
                content=resource,
            )
        try:
            is_url_broken, url_status = api.is_external_url_broken(resource)
            state.external_url_response_code = url_status
        except CheckFailedError as ex:
            log.debug(ex)
            state.status = ExternalResourceState.Status.CHECK_FAILED
        else:
            # Update the metadata of the resource with the status codes
            resource.metadata[METADATA_URL_STATUS_CODE] = url_status
            resource.save(update_fields=["metadata"])
            # Update the status based on whether the URL is broken
            if url_status not in RESOURCE_UNCHECKED_STATUSES:
                if is_url_broken:
                    # The external URL is broken
                    state.status = ExternalResourceState.Status.BROKEN
                else:
                    # The external URL is valid
                    state.status = ExternalResourceState.Status.VALID
                # Update 'is_url_broken' in metadata if it has changed
            else:
                state.status = ExternalResourceState.Status.UNCHECKED
        finally:
            state.last_checked = timezone.now()
            state.save(
                update_fields=[
                    "external_url_response_code",
                    "status",
                    "last_checked",
                ]
            )


@app.task(bind=True, acks_late=True)
def check_external_resources_for_breakages(self):
    """Check external resources for broken links."""
    external_resources = list(
        WebsiteContent.objects.filter(type=CONTENT_TYPE_EXTERNAL_RESOURCE).values_list(
            "id", flat=True
        )
    )

    tasks = [
        check_external_resources.s(resources)
        for resources in chunks(
            external_resources, chunk_size=BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK
        )
    ]
    if tasks:
        return self.replace(celery.group(tasks))

    return None
