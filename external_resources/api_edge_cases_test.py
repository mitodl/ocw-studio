"""Additional edge case tests for External Resources API"""

import pytest
from requests.exceptions import ConnectionError, Timeout
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from external_resources.api import is_url_broken
from external_resources.exceptions import CheckFailedError


def test_is_url_broken_with_timeout(mocker):
    """Test that timeout errors are properly handled"""
    mocker.patch("external_resources.api.requests.head", side_effect=Timeout())

    with pytest.raises(CheckFailedError):
        is_url_broken("http://example.com")


def test_is_url_broken_with_connection_error(mocker):
    """Test that connection errors are properly handled"""
    mocker.patch(
        "external_resources.api.requests.head", side_effect=ConnectionError()
    )

    with pytest.raises(CheckFailedError):
        is_url_broken("http://example.com")


@pytest.mark.parametrize(
    ("url", "expected_result", "expected_code"),
    [
        # Edge case: None URL
        (None, False, None),
        # Edge case: whitespace only
        ("   ", False, None),
        # Edge case: URL with spaces (invalid)
        ("http://example .com", False, None),
    ],
)
def test_is_url_broken_invalid_urls(url, expected_result, expected_code):
    """Test handling of invalid or edge case URLs"""
    result, status_code = is_url_broken(url)
    assert result == expected_result
    assert status_code == expected_code


@pytest.mark.parametrize(
    "status_code",
    [
        HTTP_500_INTERNAL_SERVER_ERROR,
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    ],
)
def test_is_url_broken_server_errors(mocker, status_code):
    """Test that server errors are properly classified as broken"""
    mock_response = mocker.Mock(status_code=status_code)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, response_code = is_url_broken("http://example.com")
    assert result is True
    assert response_code == status_code


def test_is_url_broken_redirect_chain(mocker):
    """Test handling of URLs with redirect chains"""
    mock_response = mocker.Mock(status_code=HTTP_200_OK)
    mock_response.history = [
        mocker.Mock(status_code=301),
        mocker.Mock(status_code=302),
    ]
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, status_code = is_url_broken("http://example.com")
    # After redirects, final status is 200, so URL is not broken
    assert result is False
    assert status_code == HTTP_200_OK


def test_is_url_broken_too_many_redirects(mocker):
    """Test handling of too many redirects error"""
    from requests.exceptions import TooManyRedirects

    mocker.patch(
        "external_resources.api.requests.head", side_effect=TooManyRedirects()
    )

    with pytest.raises(CheckFailedError):
        is_url_broken("http://example.com")


def test_is_url_broken_ssl_error(mocker):
    """Test handling of SSL certificate errors"""
    from requests.exceptions import SSLError

    mocker.patch("external_resources.api.requests.head", side_effect=SSLError())

    with pytest.raises(CheckFailedError):
        is_url_broken("https://example.com")


@pytest.mark.parametrize(
    ("url", "description"),
    [
        ("http://example.com/page?param=value&other=test", "URL with query params"),
        ("http://example.com/page#fragment", "URL with fragment"),
        ("http://example.com/page?param=value#fragment", "URL with both"),
        ("http://user:pass@example.com/page", "URL with authentication"),
        ("http://example.com:8080/page", "URL with custom port"),
        (
            "http://example.com/path/with/many/segments/",
            "URL with deep path structure",
        ),
    ],
)
def test_is_url_broken_complex_urls(mocker, url, description):
    """Test that complex but valid URLs are handled correctly"""
    mock_response = mocker.Mock(status_code=HTTP_200_OK)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, status_code = is_url_broken(url)
    assert result is False, f"Failed for: {description}"
    assert status_code == HTTP_200_OK


def test_is_url_broken_internationalized_domain(mocker):
    """Test handling of internationalized domain names (IDN)"""
    mock_response = mocker.Mock(status_code=HTTP_200_OK)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    # Internationalized domain (e.g., Chinese characters)
    # The URL will be encoded to punycode by the requests library
    result, status_code = is_url_broken("http://例え.jp")
    assert result is False
    assert status_code == HTTP_200_OK


def test_is_url_broken_very_long_url(mocker):
    """Test handling of very long URLs (edge case for some servers)"""
    # Create a URL with very long path
    long_path = "/".join(["segment"] * 100)
    long_url = f"http://example.com/{long_path}"

    mock_response = mocker.Mock(status_code=HTTP_200_OK)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, status_code = is_url_broken(long_url)
    assert result is False
    assert status_code == HTTP_200_OK
