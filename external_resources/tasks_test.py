"""Tests for External Resources Tasks"""

from types import SimpleNamespace
from typing import Literal

import pytest

from external_resources.exceptions import CheckFailedError
from external_resources.factories import ExternalResourceStateFactory
from external_resources.models import ExternalResourceState
from external_resources.tasks import (
    check_external_resources,
    check_external_resources_for_breakages,
)
from websites.constants import (
    BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK,
    CONTENT_TYPE_EXTERNAL_RESOURCE,
)


@pytest.mark.parametrize("webite_content_subset", [10, 110])
def test_check_external_resources_for_breakages_valid(
    mocker,
    mocked_celery: SimpleNamespace,
    webite_content_subset: Literal[10, 110],
):
    """Test for external Resource Task"""
    mock_filter = mocker.patch("websites.models.WebsiteContent.objects.filter")
    mock_filter.return_value.values_list.return_value = list(
        range(webite_content_subset)
    )

    mock_batch = mocker.patch("external_resources.tasks.check_external_resources.s")

    with pytest.raises(TabError):
        check_external_resources_for_breakages.delay()
    mock_filter.assert_called_once_with(type=CONTENT_TYPE_EXTERNAL_RESOURCE)
    assert (
        mock_batch.call_count
        == webite_content_subset // BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK
        + (
            1
            if webite_content_subset % BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK
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
        "backup_url_status",
        "backup_url_status_code",
        "resource_status",
    ),
    [
        (False, 200, False, 200, ExternalResourceState.Status.VALID),
        (False, 200, True, 400, ExternalResourceState.Status.VALID),
        (True, 400, False, 200, ExternalResourceState.Status.VALID),
        (True, 400, True, 400, ExternalResourceState.Status.BROKEN),
        (False, 200, True, 401, ExternalResourceState.Status.VALID),
        (True, 401, False, 200, ExternalResourceState.Status.VALID),
        (True, 401, True, 401, ExternalResourceState.Status.UNCHECKED),
    ],
)
def test_check_external_resources(  # noqa: PLR0913
    mocker,
    url_status,
    url_status_code,
    backup_url_status,
    backup_url_status_code,
    resource_status,
):
    """Create test data"""
    external_resource_state = ExternalResourceStateFactory()

    mocker.patch(
        "external_resources.tasks.api.is_external_url_broken",
        return_value=(url_status, url_status_code),
    )
    mocker.patch(
        "external_resources.tasks.api.is_backup_url_broken",
        return_value=(backup_url_status, backup_url_status_code),
    )
    assert external_resource_state.status == ExternalResourceState.Status.UNCHECKED

    # Run the task
    check_external_resources.delay((external_resource_state.content.id,))

    updated_state = ExternalResourceState.objects.get(id=external_resource_state.id)

    assert updated_state.status == resource_status
    assert updated_state.last_checked is not None

    assert updated_state.is_external_url_broken is url_status
    assert updated_state.is_backup_url_broken is backup_url_status

    assert updated_state.external_url_response_code == url_status_code
    assert updated_state.backup_url_response_code == backup_url_status_code

    assert updated_state.content.metadata.get("is_broken", False) is url_status


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
