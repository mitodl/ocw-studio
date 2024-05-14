import pytest

from external_resources.api import is_url_broken
from external_resources.constants import STATUS_CODE_WHITELIST
from external_resources.exceptions import CheckFailedError


def test_is_url_broken_valid(mocker):
    """Test for working url"""
    mock_response = mocker.Mock(status_code=200)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, status_code = is_url_broken("http://google.com")
    assert not result
    assert status_code == 200


@pytest.mark.parametrize("status_code", STATUS_CODE_WHITELIST)
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


def test_is_url_broken_exception(mocker):
    """Test for connection error"""
    mocker.patch(
        "external_resources.api.requests.head",
        side_effect=CheckFailedError,
    )

    with pytest.raises(CheckFailedError):
        is_url_broken("http://google.com")
