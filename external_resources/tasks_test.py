"""Tests for External Resources Tasks"""

from datetime import timedelta
from types import SimpleNamespace
from typing import Literal

import pytest
from django.utils import timezone
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from external_resources.exceptions import CheckFailedError
from external_resources.factories import ExternalResourceStateFactory
from external_resources.models import ExternalResourceState
from external_resources.tasks import (
    check_external_resources,
    check_external_resources_for_breakages,
    submit_url_to_wayback_task,
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
    assert updated_state.wayback_status == "pending"
    assert updated_state.wayback_job_id == fake_job_id
    assert updated_state.wayback_http_status is None


@pytest.mark.django_db()
def test_submit_url_to_wayback_task_skipped_due_to_recent_submission(mocker, settings):
    """
    Test that submit_url_to_wayback_task skips submission when the URL was recently submitted.
    """
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
