"""External Resources Tasks"""

import logging
from datetime import timedelta

import celery
from django.conf import settings
from django.utils import timezone
from mitol.common.utils import chunks
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    ConnectTimeout,
    HTTPError,
    Timeout,
)

from content_sync.decorators import single_task
from external_resources import api
from external_resources.constants import (
    BATCH_SIZE_WAYBACK_STATUS_UPDATE,
    EXTERNAL_RESOURCE_TASK_PRIORITY,
    EXTERNAL_RESOURCE_TASK_RATE_LIMIT,
    HTTP_TOO_MANY_REQUESTS,
    METADATA_URL_STATUS_CODE,
    POSTHOG_ENABLE_WAYBACK_TASKS,
    RESOURCE_UNCHECKED_STATUSES,
    WAYBACK_ERROR_STATUS,
    WAYBACK_MACHINE_SUBMISSION_TASK_PRIORITY,
    WAYBACK_MACHINE_TASK_RATE_LIMIT,
    WAYBACK_PENDING_STATUS,
    WAYBACK_SUCCESS_STATUS,
)
from external_resources.exceptions import CheckFailedError
from external_resources.models import ExternalResourceState
from main.celery import app
from main.posthog import is_feature_enabled
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
            # Update the status based on whether the URL is broken
            if url_status not in RESOURCE_UNCHECKED_STATUSES:
                if is_url_broken:
                    # The external URL is broken
                    state.status = ExternalResourceState.Status.BROKEN
                    resource.metadata["status"] = ExternalResourceState.Status.BROKEN
                else:
                    # The external URL is valid
                    state.status = ExternalResourceState.Status.VALID
                    resource.metadata["status"] = ExternalResourceState.Status.VALID

                    # Submit the valid URL to Wayback Machine
                    submit_url_to_wayback_task.delay(resource.id)

            else:
                state.status = ExternalResourceState.Status.UNCHECKED
                resource.metadata["status"] = ExternalResourceState.Status.UNCHECKED
        finally:
            state.last_checked = timezone.now()
            state.save(
                update_fields=[
                    "external_url_response_code",
                    "status",
                    "last_checked",
                ]
            )
            resource.save(update_fields=["metadata"])


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


@app.task(bind=True)
def submit_website_resources_to_wayback_task(
    self, website_name, ignore_last_submission=None
):
    """Submit all external resources of a website to the Wayback Machine."""
    if settings.ENABLE_WAYBACK_TASKS and is_feature_enabled(
        POSTHOG_ENABLE_WAYBACK_TASKS
    ):
        external_resources = WebsiteContent.objects.filter(
            website__name=website_name,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        ).select_related("external_resource_state")

        tasks = [
            submit_url_to_wayback_task.s(resource.id, ignore_last_submission)
            for resource in external_resources
            if ExternalResourceState.objects.get_or_create(content=resource)
        ]
        if tasks:
            return self.replace(celery.group(tasks))
        return None
    else:
        log.info(
            "Wayback Machine tasks are disabled via environment settings "
            "or PostHog feature flag."
        )
        return None


def should_skip_wayback_submission(state, ignore_last_submission=None):
    """Check if we should skip submission based on the last successful submission."""
    if ignore_last_submission:
        return False
    if state.wayback_last_successful_submission:
        retry_period = timezone.now() - timedelta(
            days=settings.WAYBACK_SUBMISSION_INTERVAL_DAYS
        )
        if state.wayback_last_successful_submission > retry_period:
            log.info(
                "Skipping submission for resource %s (ID: %s) "
                "because it was submitted less than %s days ago.",
                state.content.title,
                state.content.id,
                settings.WAYBACK_SUBMISSION_INTERVAL_DAYS,
            )
            return True
    return False


def get_external_resource_state(resource_id):
    """Get External Resource State for a given Resource ID."""
    try:
        return ExternalResourceState.objects.get(content_id=resource_id)
    except ExternalResourceState.DoesNotExist:
        log.exception(
            "ExternalResourceState does not exist for resource ID %s", resource_id
        )
        return None


@app.task(
    bind=True,
    acks_late=True,
    rate_limit=WAYBACK_MACHINE_TASK_RATE_LIMIT,
    autoretry_for=(BlockingIOError, RequestsConnectionError, Timeout),
    retry_backoff=True,
    retry_backoff_max=128,
    max_retries=7,
    priority=WAYBACK_MACHINE_SUBMISSION_TASK_PRIORITY,
)
@single_task(7)
def submit_url_to_wayback_task(self, resource_id, ignore_last_submission=None):
    """Submit an External Resource URL to the Wayback Machine."""
    if settings.ENABLE_WAYBACK_TASKS and is_feature_enabled(
        POSTHOG_ENABLE_WAYBACK_TASKS
    ):
        try:
            state = get_external_resource_state(resource_id)
            if should_skip_wayback_submission(state, ignore_last_submission):
                return
            url = state.content.metadata.get("external_url", "")
            if not url:
                log.warning(
                    "No external URL found for resource %s (ID: %s)",
                    state.content.title,
                    resource_id,
                )
                return
            log.info(
                "Submitting URL to Wayback Machine for resource '%s' (ID: %s)",
                state.content.title,
                resource_id,
            )
            response = api.submit_url_to_wayback(url)
            job_id = response.get("job_id")
            status_ext = response.get("status_ext")
            state_update_fields = ["wayback_status", "wayback_http_status"]
            state.wayback_http_status = None

            if job_id:
                state.wayback_job_id = job_id
                state.wayback_status = WAYBACK_PENDING_STATUS
                state_update_fields.append("wayback_job_id")
            else:
                state.wayback_status = WAYBACK_ERROR_STATUS
                if status_ext:
                    state.wayback_status_ext = status_ext
                    state_update_fields.append("wayback_status_ext")
                log.error(
                    "Failed to get job ID for resource %s (ID: %s). Status: %s",
                    state.content.title,
                    resource_id,
                    status_ext,
                )
            state.save(update_fields=state_update_fields)
        except HTTPError as exc:
            if exc.response.status_code == HTTP_TOO_MANY_REQUESTS:
                log.warning(
                    "HTTP 429 Too Many Requests for resource '%s' (ID: %s)."
                    "Retrying after 30 seconds.",
                    state.content.title,
                    resource_id,
                )
                raise self.retry(exc=exc, countdown=30) from exc
        except ConnectTimeout:
            log.exception(
                "Connection timed out while submitting URL to Wayback Machine "
                "for resource '%s' (ID: %s).",
                state.content.title,
                resource_id,
            )
            state.wayback_status = WAYBACK_ERROR_STATUS
            state.wayback_status_ext = "error:connect-timeout"
            state.save(update_fields=["wayback_status", "wayback_status_ext"])
        except Exception as exc:
            log.exception(
                "Error submitting URL to Wayback Machine for resource '%s' (ID: %s)",
                state.content.title,
                resource_id,
            )
            state.wayback_status = WAYBACK_ERROR_STATUS
            state.save(update_fields=["wayback_status"])
            raise self.retry(exc=exc) from exc
    else:
        return


def _get_pending_states(job_ids=None):
    """Retrieve pending states for Wayback Machine jobs."""
    if job_ids:
        return ExternalResourceState.objects.filter(
            wayback_status=WAYBACK_PENDING_STATUS,
            wayback_job_id__in=job_ids,
        )
    return ExternalResourceState.objects.filter(
        wayback_status=WAYBACK_PENDING_STATUS,
        wayback_job_id__isnull=False,
    )


@app.task(
    bind=True,
    acks_late=True,
    autoretry_for=(BlockingIOError, RequestsConnectionError, Timeout),
    retry_backoff=30,
    retry_backoff_max=240,
    max_retries=5,
)
@single_task(10)
def update_wayback_jobs_status_batch(self, job_ids=None):
    """Batch update the status of Wayback Machine jobs."""
    if settings.ENABLE_WAYBACK_TASKS and is_feature_enabled(
        POSTHOG_ENABLE_WAYBACK_TASKS
    ):
        try:
            pending_states = _get_pending_states(job_ids)
            if not pending_states.exists():
                log.info("No pending Wayback Machine jobs to update.")
                return

            job_id_to_state = {state.wayback_job_id: state for state in pending_states}

            job_ids = list(job_id_to_state.keys())

            for batch in chunks(job_ids, chunk_size=BATCH_SIZE_WAYBACK_STATUS_UPDATE):
                results = api.check_wayback_jobs_status_batch(batch)

                for result in results:
                    job_id = result.get("job_id")
                    status = result.get("status")
                    http_status = result.get("http_status")
                    status_ext = result.get("status_ext", "")
                    state = job_id_to_state.get(job_id)
                    if not state:
                        log.warning("No state found for job_id: %s", job_id)
                        continue
                    update_state_fields(state, status, http_status, status_ext, result)
                    update_metadata(state, status)
        except HTTPError as exc:
            if exc.response.status_code == HTTP_TOO_MANY_REQUESTS:
                log.warning(
                    "HTTP 429 Too Many Requests when trying to update "
                    "Wayback Machine job statuses. Retrying after 30 seconds."
                )
                raise self.retry(exc=exc, countdown=30) from exc
        except ConnectTimeout:
            log.exception(
                "Connection timed out while updating Wayback Machine job statuses."
            )
        except Exception as exc:
            log.exception("Error during batch status update of Wayback Machine jobs")
            raise self.retry(exc=exc) from exc
    else:
        log.info(
            "Wayback Machine tasks are disabled via environment settings "
            "or PostHog feature flag."
        )
        return


def update_state_fields(state, wayback_status, http_status, status_ext, result):
    """Update state fields based on Wayback Machine result."""
    state.wayback_status = wayback_status
    state_update_fields = ["wayback_status"]

    state.wayback_http_status = http_status
    state_update_fields.append("wayback_http_status")

    if wayback_status == WAYBACK_SUCCESS_STATUS:
        state.wayback_url = generate_wayback_url(result)
        state.wayback_last_successful_submission = timezone.now()
        state_update_fields.extend(
            ["wayback_url", "wayback_last_successful_submission"]
        )
        log.info(
            "Wayback Machine job %s succeeded for resource %s (ID: %s)",
            state.wayback_job_id,
            state.content.title,
            state.content_id,
        )

    elif wayback_status == WAYBACK_ERROR_STATUS:
        state.wayback_status_ext = status_ext
        state_update_fields.append("wayback_status_ext")
        log.error(
            "Wayback Machine job %s failed for resource %s (ID: %s) with status_ext %s",
            state.wayback_job_id,
            state.content.title,
            state.content_id,
            status_ext,
        )
    elif wayback_status == WAYBACK_PENDING_STATUS:
        log.info(
            "Wayback Machine job %s is still pending for resource %s (ID: %s)",
            state.wayback_job_id,
            state.content.title,
            state.content_id,
        )

    state.save(update_fields=state_update_fields)


def update_metadata(state, wayback_status):
    """Update metadata for the resource if applicable."""
    if wayback_status == WAYBACK_SUCCESS_STATUS:
        resource = state.content
        resource.metadata["wayback_url"] = state.wayback_url
        resource.save(update_fields=["metadata"])


def generate_wayback_url(result):
    """Generate the Wayback Machine URL."""
    timestamp = result.get("timestamp")
    original_url = result.get("original_url")
    return f"https://web.archive.org/web/{timestamp}/{original_url}"
