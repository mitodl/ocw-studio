"""Tests for the backpopulate_pipelines management command."""  # noqa: INP001

import pytest
from django.core.management import CommandError, call_command

from users.factories import UserFactory
from websites.factories import WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_upsert_pipelines(mocker, settings):
    """Mock the background pipeline job."""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    mock_delay = mocker.patch(
        "content_sync.management.commands.backpopulate_pipelines.upsert_pipelines.delay"
    )
    mock_delay.return_value.get.return_value = [True]
    return mock_delay


@pytest.mark.parametrize("create_backend", [True, False])
def test_pipeline_upsert_passes_commit_user(mock_upsert_pipelines, create_backend):
    """Only the mode that syncs content needs a user."""
    website = WebsiteFactory.create()
    user = UserFactory.create() if create_backend else None

    call_command(
        "backpopulate_pipelines",
        filter=website.name,
        create_backend=create_backend,
        user=user.email if user else None,
    )

    mock_upsert_pipelines.assert_called_once_with(
        [website.name],
        chunk_size=500,
        create_backend=create_backend,
        unpause=False,
        hugo_args="",
        commit_user_id=user.pk if user else None,
    )


@pytest.mark.parametrize("inactive", [True, False])
def test_create_backend_requires_active_user(mock_upsert_pipelines, mocker, inactive):
    """Reject inactive or missing users before changing pipelines."""
    mock_pipeline_api = mocker.patch(
        "content_sync.management.commands.backpopulate_pipelines.get_pipeline_api"
    )
    user_email = UserFactory.create(is_active=False).email if inactive else None

    with pytest.raises(CommandError, match="--user"):
        call_command(
            "backpopulate_pipelines",
            create_backend=True,
            delete_all=True,
            user=user_email,
        )

    mock_pipeline_api.assert_not_called()
    mock_upsert_pipelines.assert_not_called()
