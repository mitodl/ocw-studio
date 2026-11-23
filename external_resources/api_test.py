"""Tests for External Resources API"""

import pytest
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    InvalidURL,
    SSLError,
    Timeout,
    TooManyRedirects,
)
from rest_framework.status import HTTP_200_OK

from external_resources.api import is_url_broken
from external_resources.constants import RESOURCE_UNCHECKED_STATUSES
from external_resources.exceptions import CheckFailedError


def test_is_url_broken_valid(mocker):
    """Test for working url"""
    mock_response = mocker.Mock(status_code=HTTP_200_OK)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, status_code = is_url_broken("http://google.com")
    assert not result
    assert status_code == HTTP_200_OK


@pytest.mark.parametrize("status_code", RESOURCE_UNCHECKED_STATUSES)
def test_is_url_broken_whitelisted(mocker, status_code):
    """Test for broken url"""
    mock_response = mocker.Mock(status_code=status_code)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, response_status_code = is_url_broken("http://google.com/")
    assert result
    assert response_status_code == status_code


def test_is_url_broken_empty():
    """Test for empty url"""
    result, status_code = is_url_broken("")
    assert not result
    assert status_code is None


@pytest.mark.parametrize(
    "error", [RequestsConnectionError, Timeout, SSLError, TooManyRedirects, InvalidURL]
)
def test_is_url_broken_exception(mocker, error):
    """Request errors should be raised as CheckFailedError"""
    mocker.patch(
        "external_resources.api.requests.head",
        side_effect=error,
    )

    with pytest.raises(CheckFailedError) as exc_info:
        is_url_broken("http://google.com")
    assert isinstance(exc_info.value.__cause__, error)
