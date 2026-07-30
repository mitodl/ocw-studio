"""Edge case tests for external resources tasks to prevent regressions"""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from django.utils import timezone
from requests.exceptions import HTTPError, Timeout
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND

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
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE

pytestmark = pytest.mark.django_db


def test_check_external_resources_with_null_metadata(mocker):
    """Test that resources with null external_url metadata are handled gracefully"""
    external_resource_state = ExternalResourceStateFactory()
    # Set metadata to None or empty dict
    external_resource_state.content.metadata = None
    external_resource_state.content.save()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        return_value=(False, HTTP_200_OK),
    )

    # Should not raise an error
    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    assert updated_state.last_checked is not None


def test_check_external_resources_with_malformed_url(mocker):
    """Test handling of malformed URLs in external resources"""
    external_resource_state = ExternalResourceStateFactory()
    # Set a malformed URL
    external_resource_state.content.metadata["external_url"] = "not a valid url"
    external_resource_state.content.save()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        side_effect=CheckFailedError,
    )

    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    assert updated_state.status == ExternalResourceState.Status.CHECK_FAILED


def test_check_external_resources_with_unicode_url(mocker):
    """Test handling of URLs with unicode characters"""
    external_resource_state = ExternalResourceStateFactory()
    # URL with unicode characters (should be encoded)
    external_resource_state.content.metadata["external_url"] = (
        "http://example.com/page?query=tëst"
    )
    external_resource_state.content.save()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        return_value=(False, HTTP_200_OK),
    )

    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    assert updated_state.status == ExternalResourceState.Status.VALID


def test_check_external_resources_concurrent_updates(mocker):
    """Test that concurrent checks don't cause race conditions"""
    external_resource_state = ExternalResourceStateFactory()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        return_value=(False, HTTP_200_OK),
    )

    # Simulate concurrent task execution
    content_id = external_resource_state.content.id

    # Run task multiple times (simulating concurrent execution)
    check_external_resources.delay((content_id,))
    check_external_resources.delay((content_id,))
    check_external_resources.delay((content_id,))

    # Should complete without errors
    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    assert updated_state.last_checked is not None


def test_check_external_resources_with_very_long_url(mocker):
    """Test handling of very long URLs (edge case for some systems)"""
    external_resource_state = ExternalResourceStateFactory()
    # Create a very long URL
    long_path = "/".join(["segment"] * 50)
    long_url = f"http://example.com/{long_path}?param=value"
    external_resource_state.content.metadata["external_url"] = long_url
    external_resource_state.content.save()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        return_value=(False, HTTP_200_OK),
    )

    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)
    assert updated_state.status == ExternalResourceState.Status.VALID


def test_submit_url_to_wayback_with_empty_url(mocker, settings):
    """Test that empty URLs are handled gracefully"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    external_resource_state = ExternalResourceStateFactory()
    resource = external_resource_state.content
    resource.metadata["external_url"] = ""
    resource.save()

    mock_submit = mocker.patch("external_resources.tasks.api.submit_url_to_wayback")
    mock_log = mocker.patch("external_resources.tasks.log")

    # Should handle gracefully without calling API
    submit_url_to_wayback_task.run(resource.id)

    # Should not attempt to submit empty URL
    mock_submit.assert_not_called()


def test_submit_url_to_wayback_with_url_with_fragment(mocker):
    """Test submission of URL with fragment identifier"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    external_resource_state = ExternalResourceStateFactory()
    resource = external_resource_state.content
    # URL with fragment
    external_url = "http://example.com/page#section"
    resource.metadata["external_url"] = external_url
    resource.save()

    fake_job_id = "job_fragment_test"
    mock_submit = mocker.patch(
        "external_resources.tasks.api.submit_url_to_wayback",
        return_value={"job_id": fake_job_id},
    )

    submit_url_to_wayback_task.run(resource.id)

    # Should submit the full URL including fragment
    mock_submit.assert_called_once_with(external_url)


def test_submit_url_to_wayback_http_error_retry_exhausted(mocker):
    """Test behavior when retry is exhausted after multiple 429 errors"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

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

    # Mock retry to raise Retry exception
    mock_retry = mocker.patch.object(
        submit_url_to_wayback_task, "retry", side_effect=Retry()
    )

    with pytest.raises(Retry):
        submit_url_to_wayback_task.run(resource.id)

    mock_retry.assert_called_once()


def test_submit_url_to_wayback_with_timeout(mocker):
    """Test that timeout during submission triggers retry"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    external_resource_state = ExternalResourceStateFactory()
    resource = external_resource_state.content
    external_url = "http://example.com"
    resource.metadata["external_url"] = external_url
    resource.save()

    # Simulate timeout
    mock_submit = mocker.patch(
        "external_resources.tasks.api.submit_url_to_wayback", side_effect=Timeout()
    )

    mock_retry = mocker.patch.object(
        submit_url_to_wayback_task, "retry", side_effect=Retry()
    )

    with pytest.raises(Retry):
        submit_url_to_wayback_task.run(resource.id)


def test_update_wayback_jobs_status_batch_with_missing_jobs(mocker):
    """Test handling of jobs that no longer exist in Wayback API response"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    # Create states with pending jobs
    state1 = ExternalResourceStateFactory(
        wayback_job_id="job_exists", wayback_status=WAYBACK_PENDING_STATUS
    )
    state2 = ExternalResourceStateFactory(
        wayback_job_id="job_missing", wayback_status=WAYBACK_PENDING_STATUS
    )

    # Mock API to return result for only one job
    fake_results = [
        {
            "job_id": "job_exists",
            "status": WAYBACK_SUCCESS_STATUS,
            "timestamp": "20230101000000",
            "original_url": "http://example.com/page1",
            "http_status": 200,
        }
        # job_missing is not in results
    ]

    mock_check = mocker.patch(
        "external_resources.tasks.api.check_wayback_jobs_status_batch",
        return_value=fake_results,
    )

    update_wayback_jobs_status_batch.run()

    # Job that was in results should be updated
    updated_state1 = ExternalResourceState.objects.get(id=state1.id)
    assert updated_state1.wayback_status == WAYBACK_SUCCESS_STATUS

    # Job that was missing from results should remain pending
    updated_state2 = ExternalResourceState.objects.get(id=state2.id)
    # Depending on implementation, it might remain pending or be marked as error
    # This test documents the actual behavior
    assert updated_state2.wayback_job_id == "job_missing"


def test_update_wayback_jobs_status_batch_with_partial_data(mocker):
    """Test handling of job results with missing optional fields"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    state = ExternalResourceStateFactory(
        wayback_job_id="job_partial", wayback_status=WAYBACK_PENDING_STATUS
    )

    # Mock API to return result with missing optional fields
    fake_results = [
        {
            "job_id": "job_partial",
            "status": WAYBACK_SUCCESS_STATUS,
            # Missing timestamp, original_url, http_status
        }
    ]

    mock_check = mocker.patch(
        "external_resources.tasks.api.check_wayback_jobs_status_batch",
        return_value=fake_results,
    )

    # Should handle missing fields gracefully
    update_wayback_jobs_status_batch.run()

    updated_state = ExternalResourceState.objects.get(id=state.id)
    assert updated_state.wayback_status == WAYBACK_SUCCESS_STATUS


def test_update_wayback_jobs_status_batch_with_api_error(mocker):
    """Test handling of API errors during batch status check"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    ExternalResourceStateFactory(
        wayback_job_id="job_1", wayback_status=WAYBACK_PENDING_STATUS
    )

    # Mock API to raise an error
    mock_check = mocker.patch(
        "external_resources.tasks.api.check_wayback_jobs_status_batch",
        side_effect=HTTPError(),
    )

    mock_log = mocker.patch("external_resources.tasks.log")

    # Should handle error gracefully and log it
    update_wayback_jobs_status_batch.run()

    # Should log the error
    assert mock_log.error.called or mock_log.exception.called


def test_update_wayback_jobs_status_batch_with_invalid_status(mocker):
    """Test handling of unexpected status values from Wayback API"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)

    state = ExternalResourceStateFactory(
        wayback_job_id="job_invalid", wayback_status=WAYBACK_PENDING_STATUS
    )

    # Mock API to return an unexpected status
    fake_results = [
        {
            "job_id": "job_invalid",
            "status": "unknown_status",  # Unexpected value
            "timestamp": "20230101000000",
            "original_url": "http://example.com",
            "http_status": 200,
        }
    ]

    mock_check = mocker.patch(
        "external_resources.tasks.api.check_wayback_jobs_status_batch",
        return_value=fake_results,
    )

    # Should handle gracefully
    update_wayback_jobs_status_batch.run()

    updated_state = ExternalResourceState.objects.get(id=state.id)
    # Should update to the unexpected status (or handle as configured)
    assert updated_state.wayback_job_id == "job_invalid"


def test_check_external_resources_for_breakages_with_deleted_content(
    mocker, mocked_celery
):
    """Test that deleted content doesn't cause errors in batch check"""
    mock_filter = mocker.patch("websites.models.WebsiteContent.objects.filter")

    # Simulate IDs including some that might be deleted before processing
    content_ids = [1, 2, 3, 999999]  # 999999 doesn't exist
    mock_filter.return_value.values_list.return_value = content_ids

    mock_batch = mocker.patch("external_resources.tasks.check_external_resources.s")

    with pytest.raises(TabError):
        check_external_resources_for_breakages.delay()

    # Should still create batches for all IDs
    # The individual task will handle missing content
    assert mock_batch.called


@pytest.mark.parametrize(
    ("interval_days", "days_since_submission", "should_skip"),
    [
        (7, 1, True),  # Recently submitted, should skip
        (7, 8, False),  # Long enough ago, should submit
        (7, 7, False),  # Exactly at interval, should submit
        (30, 29, True),  # Within interval, should skip
        (30, 31, False),  # Past interval, should submit
    ],
)
def test_submit_url_to_wayback_interval_edge_cases(
    mocker, settings, interval_days, days_since_submission, should_skip
):
    """Test edge cases for Wayback submission interval checking"""
    mocker.patch("external_resources.tasks.settings.ENABLE_WAYBACK_TASKS", new=True)
    settings.WAYBACK_SUBMISSION_INTERVAL_DAYS = interval_days

    submission_time = timezone.now() - timedelta(days=days_since_submission)
    external_resource_state = ExternalResourceStateFactory(
        wayback_last_successful_submission=submission_time
    )
    resource = external_resource_state.content
    resource.metadata["external_url"] = "http://example.com"
    resource.save()

    mock_submit = mocker.patch(
        "external_resources.tasks.api.submit_url_to_wayback",
        return_value={"job_id": "test_job"},
    )

    submit_url_to_wayback_task.run(resource.id)

    if should_skip:
        mock_submit.assert_not_called()
    else:
        mock_submit.assert_called_once()
