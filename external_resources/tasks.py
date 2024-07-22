"""External Resources Tasks"""

import logging

import celery
from django.utils import timezone
from mitol.common.utils import chunks

from external_resources import api
from external_resources.constants import (
    EXTERNAL_RESOURCE_TASK_PRIORITY,
    EXTERNAL_RESOURCE_TASK_RATE_LIMIT,
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
            state.is_external_url_broken = is_url_broken

            # If url is broken, check backup url for the resource
            is_backup_url_broken, backup_url_status = api.is_backup_url_broken(resource)
            state.backup_url_response_code = backup_url_status
            state.is_backup_url_broken = is_backup_url_broken
        except CheckFailedError as ex:
            log.debug(ex)
            state.status = ExternalResourceState.Status.CHECK_FAILED
        else:
            if (
                url_status not in RESOURCE_UNCHECKED_STATUSES
                or backup_url_status not in RESOURCE_UNCHECKED_STATUSES
            ):
                is_broken = is_url_broken and (
                    backup_url_status is None or is_backup_url_broken
                )
                if is_broken:
                    # both external_url and backup_url are broken.
                    state.status = ExternalResourceState.Status.BROKEN
                else:
                    # Either external_url or backup_url is valid.
                    state.status = ExternalResourceState.Status.VALID

                if resource.metadata.get("is_broken") != is_broken:
                    resource.metadata["is_broken"] = is_broken
                    resource.save()
        finally:
            state.last_checked = timezone.now()

        state.save()


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
        raise self.replace(celery.group(tasks))
