""" Content sync signals tests """

import pytest

from websites.factories import WebsiteContentFactory


pytestmark = pytest.mark.django_db


def test_create_content_sync_state(mocker):
    """ Test that the create_content_sync_state signal makes the correct call """
    mock_api = mocker.patch("content_sync.signals.api", autospec=True)
    content = WebsiteContentFactory.create()
    mock_api.upsert_content_sync_state.assert_called_once_with(content)
    content.save()
    assert mock_api.upsert_content_sync_state.call_count == 2
    mock_api.upsert_content_sync_state.assert_has_calls(
        [mocker.call(content), mocker.call(content)]
    )
