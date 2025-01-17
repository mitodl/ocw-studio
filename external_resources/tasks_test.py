"""Tests for External Resources Tasks"""

from datetime import timedelta
from types import SimpleNamespace
from typing import Literal
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from django.utils import timezone
from requests.exceptions import HTTPError
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from external_resources.constants import (
    HTTP_TOO_MANY_REQUESTS,
    WAYBACK_ERROR_STATUS,
    WAYBACK_PENDING_STATUS,
    WAYBACK_SUCCESS_STATUS,
)
from external_resources.exceptions import CheckFailedError
from external_resources.factories import ExternalResourceStateFactory
from external_resources.models import ExternalResourceState
from external_resources.tasks import (
    check_external_resources,
    check_external_resources_for_breakages,
    submit_url_to_wayback_task,
    update_wayback_jobs_status_batch,
)
from websites.constants import (
    BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK,
    CONTENT_TYPE_EXTERNAL_RESOURCE,
)


@pytest.mark.parametrize("website_content_subset", [10, 110])
def test_check_external_resources_for_breakages_valid(
    mocker,
    mocked_celery: SimpleNamespace,
    website_content_subset: Literal[10, 110],
):
    """Test for external Resource Task"""
    mock_filter = mocker.patch("websites.models.WebsiteContent.objects.filter")
    mock_filter.return_value.values_list.return_value = list(
        range(website_content_subset)
    )

    mock_batch = mocker.patch("external_resources.tasks.check_external_resources.s")

    with pytest.raises(TabError):
        check_external_resources_for_breakages.delay()
    mock_filter.assert_called_once_with(type=CONTENT_TYPE_EXTERNAL_RESOURCE)
    assert (
        mock_batch.call_count
        == website_content_subset // BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK
        + (
            1
            if website_content_subset % BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK
            else 0
        )
    )
    assert mocked_celery.group.call_count == 1
    assert mocked_celery.replace.call_count == 1


def test_check_external_resources_for_breakages_zero_websites(
    mocker, mocked_celery: SimpleNamespace
):
    """Test for external Resource Task"""
    mock_filter = mocker.patch("websites.models.WebsiteContent.objects.filter")
    mock_filter.return_value.values_list.return_value = []

    mock_batch = mocker.patch("external_resources.tasks.check_external_resources.s")

    assert mock_batch.call_count == 0
    assert mocked_celery.group.call_count == 0
    assert mocked_celery.replace.call_count == 0


@pytest.mark.django_db()
@pytest.mark.parametrize(
    (
        "url_status",
        "url_status_code",
        "expected_status",
    ),
    [
        (False, HTTP_200_OK, ExternalResourceState.Status.VALID),
        (True, HTTP_400_BAD_REQUEST, ExternalResourceState.Status.BROKEN),
        (True, HTTP_401_UNAUTHORIZED, ExternalResourceState.Status.UNCHECKED),
        (True, HTTP_403_FORBIDDEN, ExternalResourceState.Status.UNCHECKED),
        (True, HTTP_404_NOT_FOUND, ExternalResourceState.Status.BROKEN),
    ],
)
def test_check_external_resources(
    mocker,
    url_status,
    url_status_code,
    expected_status,
):
    """Create test data"""
    external_resource_state = ExternalResourceStateFactory()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        return_value=(url_status, url_status_code),
    )

    # Run the task
    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)

    assert updated_state.last_checked is not None
    assert updated_state.status == expected_status
    assert updated_state.external_url_response_code == url_status_code


@pytest.mark.django_db()
def test_check_external_resources_failed(mocker):
    """Test for failed api check"""
    external_resource_state = ExternalResourceStateFactory()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        side_effect=CheckFailedError,
    )

    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)

    assert updated_state.status == ExternalResourceState.Status.CHECK_FAILED


@pytest.mark.django_db()
def test_submit_url_to_wayback_task_success(mocker):
    """
    Test that submit_url_to_wayback_task successfully submits a URL to the Wayback Machine
    and updates the ExternalResourceState accordingly.
    """
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)
    mocker.patch("external_resources.tasks.is_feature_enabled", return_value=True)

    external_resource_state = ExternalResourceStateFactory()
    resource = external_resource_state.content

    external_url = "http://example.com"
    resource.metadata["external_url"] = external_url
    resource.save()

    fake_job_id = "job_12345"
    mock_submit = mocker.patch(
        "external_resources.tasks.api.submit_url_to_wayback",
        return_value={"job_id": fake_job_id},
    )

    # Run the task synchronously
    submit_url_to_wayback_task.run(resource.id)

    mock_submit.assert_called_once_with(external_url)

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    # Check that the state was updated correctly
    assert updated_state.wayback_status == WAYBACK_PENDING_STATUS
    assert updated_state.wayback_job_id == fake_job_id
    assert updated_state.wayback_http_status is None


@pytest.mark.django_db()
def test_submit_url_to_wayback_task_skipped_due_to_recent_submission(mocker, settings):
    """
    Test that submit_url_to_wayback_task skips submission when the URL was recently submitted.
    """
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)
    mocker.patch("external_resources.tasks.is_feature_enabled", return_value=True)

    settings.WAYBACK_SUBMISSION_INTERVAL_DAYS = 7

    # Create an ExternalResourceState with a recent wayback_last_successful_submission
    recent_submission_time = timezone.now() - timedelta(days=1)  # 1 day ago
    external_resource_state = ExternalResourceStateFactory(
        wayback_last_successful_submission=recent_submission_time,
    )
    resource = external_resource_state.content
    external_url = "http://example.com"
    resource.metadata["external_url"] = external_url
    resource.save()

    mock_submit = mocker.patch("external_resources.tasks.api.submit_url_to_wayback")

    # Mock the logger to capture log messages
    mock_log = mocker.patch("external_resources.tasks.log")

    # Run the task synchronously
    submit_url_to_wayback_task.run(resource.id)

    mock_submit.assert_not_called()

    # Check that a log message was made about skipping submission
    mock_log.info.assert_called_once()
    log_call_args = mock_log.info.call_args[0]
    assert "Skipping submission for resource" in log_call_args[0]

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    # wayback_status and wayback_job_id should remain unchanged
    assert updated_state.wayback_status == external_resource_state.wayback_status
    assert updated_state.wayback_job_id == external_resource_state.wayback_job_id


@pytest.mark.django_db()
def test_submit_url_to_wayback_task_http_error_429(mocker):
    """
    Test that submit_url_to_wayback_task retries on HTTPError 429 (Too Many Requests).
    """
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)
    mocker.patch("external_resources.tasks.is_feature_enabled", return_value=True)

    external_resource_state = ExternalResourceStateFactory()
    resource = external_resource_state.content
    external_url = "http://example.com"
    resource.metadata["external_url"] = external_url
    resource.save()

    mock_response = Mock()
    mock_response.status_code = HTTP_TOO_MANY_REQUESTS
    http_error_429 = HTTPError(response=mock_response)

    mock_submit = mocker.patch(
        "external_resources.tasks.api.submit_url_to_wayback",
        side_effect=http_error_429,
    )

    mock_retry = mocker.patch.object(
        submit_url_to_wayback_task, "retry", side_effect=Retry()
    )

    # Run the task synchronously and expect a Retry exception
    with pytest.raises(Retry):
        submit_url_to_wayback_task.run(resource.id)

    # Check that api.submit_url_to_wayback was called
    mock_submit.assert_called_once_with(external_url)

    # Check that self.retry was called with countdown=30
    mock_retry.assert_called_once_with(exc=http_error_429, countdown=30)


@pytest.mark.django_db()
def test_update_wayback_jobs_status_batch_success(mocker):
    """
    Test that update_wayback_jobs_status_batch updates statuses of pending jobs successfully.
    """
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)
    mocker.patch("external_resources.tasks.is_feature_enabled", return_value=True)

    # Create ExternalResourceState objects with pending Wayback Machine jobs
    state1 = ExternalResourceStateFactory(
        wayback_job_id="job_1",
        wayback_status=WAYBACK_PENDING_STATUS,
    )
    state2 = ExternalResourceStateFactory(
        wayback_job_id="job_2",
        wayback_status=WAYBACK_PENDING_STATUS,
    )

    # Mock api.check_wayback_jobs_status_batch to return fake results
    fake_results = [
        {
            "job_id": "job_1",
            "status": WAYBACK_SUCCESS_STATUS,
            "timestamp": "20230101000000",
            "original_url": "http://example.com/page1",
            "http_status": 200,
        },
        {
            "job_id": "job_2",
            "status": WAYBACK_ERROR_STATUS,
            "status_ext": "error:404",
            "http_status": 404,
        },
    ]
    mock_check = mocker.patch(
        "external_resources.tasks.api.check_wayback_jobs_status_batch",
        return_value=fake_results,
    )

    update_wayback_jobs_status_batch.run()

    # Check that api.check_wayback_jobs_status_batch was called with correct job_ids
    expected_job_ids = ["job_1", "job_2"]
    mock_check.assert_called()
    call_args = mock_check.call_args[0][0]
    assert set(call_args) == set(expected_job_ids)

    # Fetch updated states
    updated_state1 = ExternalResourceState.objects.get(id=state1.id)
    updated_state2 = ExternalResourceState.objects.get(id=state2.id)

    # Verify that state1 was updated to success
    assert updated_state1.wayback_status == WAYBACK_SUCCESS_STATUS
    assert (
        updated_state1.wayback_url
        == "https://web.archive.org/web/20230101000000/http://example.com/page1"
    )
    assert updated_state1.wayback_last_successful_submission is not None

    # Verify that state2 was updated to error
    assert updated_state2.wayback_status == WAYBACK_ERROR_STATUS
    assert updated_state2.wayback_status_ext == "error:404"
    assert updated_state2.wayback_http_status == 404


@pytest.mark.django_db()
def test_update_wayback_jobs_status_batch_no_pending_jobs(mocker):
    """
    Test that update_wayback_jobs_status_batch handles no pending jobs gracefully.
    """
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)
    mocker.patch("external_resources.tasks.is_feature_enabled", return_value=True)

    # Ensure there are no ExternalResourceState instances with wayback_status "pending"
    ExternalResourceState.objects.filter(wayback_status=WAYBACK_PENDING_STATUS).delete()

    mock_check = mocker.patch(
        "external_resources.tasks.api.check_wayback_jobs_status_batch"
    )
    mock_log = mocker.patch("external_resources.tasks.log")

    update_wayback_jobs_status_batch.run()
    mock_check.assert_not_called()
    mock_log.info.assert_called_once_with("No pending Wayback Machine jobs to update.")
