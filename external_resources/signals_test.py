"""External Resources signals tests"""

import pytest

from external_resources.models import ExternalResourceState
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.factories import WebsiteContentFactory


@pytest.mark.django_db()
def test_upsert_external_resource_state(mocker):
    """Test that the upsert_external_resource_state signal makes the correct call"""
    mock_update_or_create = mocker.patch(
        "external_resources.signals.ExternalResourceState.objects.update_or_create",
        autospec=True,
    )
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_EXTERNAL_RESOURCE)
    mock_update_or_create.assert_called_once_with(
        content=content,
        defaults={
            "status": ExternalResourceState.Status.UNCHECKED,
            "last_checked": None,
            "external_url_response_code": None,
            "wayback_job_id": "",
            "wayback_status": "",
            "wayback_url": "",
        },
    )
    content.save()
    assert mock_update_or_create.call_count == 2
    mock_update_or_create.assert_has_calls(
        [
            mocker.call(
                content=content,
                defaults={
                    "status": ExternalResourceState.Status.UNCHECKED,
                    "last_checked": None,
                    "external_url_response_code": None,
                    "wayback_job_id": "",
                    "wayback_status": "",
                    "wayback_url": "",
                },
            ),
            mocker.call(
                content=content,
                defaults={
                    "status": ExternalResourceState.Status.UNCHECKED,
                    "last_checked": None,
                    "external_url_response_code": None,
                    "wayback_job_id": "",
                    "wayback_status": "",
                    "wayback_url": "",
                },
            ),
        ]
    )
